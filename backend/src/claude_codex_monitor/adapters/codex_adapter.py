"""Codex CLI provider adapter.

Discovery is self-contained (vendor/codex_appserver/discovery.py). Usage
comes from actively spawning `codex [--profile X] app-server --stdio` with
an explicit per-profile timeout and isolated environment
(vendor/codex_appserver/app_server_client.py) - real on-demand probing, not
DB reads. In practice only the "primary" window is reliably present;
"secondary" often absent, which must render as unavailable, never zero.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus, sanitize_path
from ..models.usage import DataQuality, UsageLimit
from ..vendor.codex_appserver import discovery as codex_discovery
from ..vendor.codex_appserver.app_server_client import probe_profile
from ..vendor.codex_appserver.models import CodexProfileCandidate, ProbeResult

LOGGER = logging.getLogger("claude_codex_monitor.adapters.codex")

_PROBE_TIMEOUT_SECONDS = 18.0

_WINDOW_LABELS = {"primary": "Primary", "secondary": "Secondary"}


def _candidate_key(c: CodexProfileCandidate) -> str:
    base = str(c.codex_home).lower()
    if c.profile_arg:
        base += f"::{c.profile_arg}"
    return base


class CodexProviderAdapter:
    provider_name = "codex"

    def __init__(self) -> None:
        self._candidates_by_id: dict[str, CodexProfileCandidate] = {}

    def _refresh_candidates(self) -> list[CodexProfileCandidate]:
        candidates = codex_discovery.discover_profiles()
        self._candidates_by_id = {_candidate_key(c): c for c in candidates}
        return candidates

    def discover_profiles(self) -> list[ProfileStatus]:
        candidates = self._refresh_candidates()
        profiles: list[ProfileStatus] = []
        for c in candidates:
            profile_id = _candidate_key(c)
            profiles.append(
                ProfileStatus(
                    provider=self.provider_name,
                    profile_id=profile_id,
                    profile_key=f"{self.provider_name}:{profile_id}",
                    label=c.label,
                    sanitized_source=sanitize_path(str(c.codex_home)),
                    discovery_source=c.source,
                    is_active=True,
                    executable_found=c.codex_executable is not None,
                )
            )
        return profiles

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        if not self._candidates_by_id:
            self._refresh_candidates()
        c = self._candidates_by_id.get(profile.profile_id)
        if c is None:
            return False, "profile no longer discoverable"
        credible = codex_discovery.credible_home(c.codex_home)
        return credible, "credible home" if credible else "home directory missing signals"

    def fetch_usage(self, profile: ProfileStatus) -> ProbeResult:
        if not self._candidates_by_id:
            self._refresh_candidates()
        candidate = self._candidates_by_id.get(profile.profile_id)
        if candidate is None:
            return ProbeResult(
                profile=CodexProfileCandidate(
                    label=profile.label, kind="unknown", codex_home=None  # type: ignore[arg-type]
                ),
                ok=False,
                error="profile no longer discoverable",
            )
        if candidate.codex_executable is None:
            return ProbeResult(profile=candidate, ok=False, error="codex executable not found on PATH")
        return probe_profile(candidate, timeout=_PROBE_TIMEOUT_SECONDS)

    def parse_usage(self, profile: ProfileStatus, raw: ProbeResult) -> list[UsageLimit]:
        now = datetime.now(UTC)
        if not raw.ok:
            reason = raw.error or "Codex app-server probe failed"
            if "auth" in (raw.error or "").lower() or "unauthenticated" in (raw.error or "").lower():
                reason = "Authentication required. Run `codex login` for this profile."
            return [
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason=reason,
                    observed_at_utc=now,
                )
            ]

        if not raw.rate_limits:
            return [
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason="Codex app-server returned no rate-limit windows for this account.",
                    observed_at_utc=now,
                )
            ]

        results: list[UsageLimit] = []
        for w in raw.rate_limits:
            used_percent = float(w.used_percent) if w.used_percent is not None else None
            remaining_percent = None
            quality = DataQuality.VERIFIED
            reason = None
            if used_percent is None:
                quality = DataQuality.UNAVAILABLE
                window_label = _WINDOW_LABELS.get(w.window_name, w.window_name)
                reason = f"{window_label} window present but no usedPercent reported."
            else:
                remaining_percent = max(0.0, 100.0 - used_percent)

            results.append(
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id=w.window_name,
                    window_label=_WINDOW_LABELS.get(w.window_name, w.window_name),
                    window_duration_minutes=w.window_duration_mins,
                    used_percent=used_percent,
                    remaining_percent=remaining_percent,
                    resets_at_utc=w.resets_at,
                    reset_confirmed=False,
                    quality=quality,
                    unavailable_reason=reason,
                    observed_at_utc=now,
                    source_detail={
                        "plan_type": w.plan_type,
                        "raw_limit_name": w.raw_limit_name,
                        "limit_id": w.limit_id,
                        "account_label": raw.account_label,
                        "source": "codex_app_server_live_probe",
                    },
                )
            )
        return results

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        if not self._candidates_by_id:
            self._refresh_candidates()
        candidate = self._candidates_by_id.get(profile.profile_id)
        if candidate is None:
            return {}
        result = self.fetch_usage(profile)
        if result.ok:
            return {"account_label": result.account_label}
        return {}

    def diagnose_error(self, profile: ProfileStatus, error: Exception | str) -> ProfileDiagnostics:
        candidate = self._candidates_by_id.get(profile.profile_id)
        exe_sanitized = None
        if candidate and candidate.codex_executable:
            exe_sanitized = sanitize_path(str(candidate.codex_executable))
        suggested = "Run `codex login` if authentication is required, or check that codex.exe is on PATH."
        error_text = str(error)[:300] if error else None
        if error_text and "timeout" in error_text.lower():
            suggested = (
                "The app-server probe timed out; the profile may be unresponsive or under load. "
                "Retry later."
            )
        return ProfileDiagnostics(
            provider=self.provider_name,
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            last_command_result=None,
            parser_used="codex_app_server_client",
            current_error=error_text,
            suggested_action=suggested,
            executable_path_sanitized=exe_sanitized,
        )
