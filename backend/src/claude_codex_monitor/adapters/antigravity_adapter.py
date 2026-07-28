"""Google Antigravity provider adapter."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus, sanitize_path
from ..models.usage import DataQuality, UsageLimit
from ..vendor.antigravity import discovery as antigravity_discovery
from ..vendor.antigravity.models import AntigravityProfileCandidate
from ..vendor.antigravity.usage_command import (
    AntigravityUsageCommandResult,
    read_usage_snapshot,
    run_usage_command,
    usage_snapshot_path,
)


def _candidate_key(c: AntigravityProfileCandidate) -> str:
    base = str(c.config_home).lower()
    if c.project_id:
        base += f"::project:{c.project_id}"
    if c.profile_arg:
        base += f"::profile:{c.profile_arg}"
    return base


class AntigravityProviderAdapter:
    provider_name = "antigravity"

    def __init__(self) -> None:
        self._candidates_by_id: dict[str, AntigravityProfileCandidate] = {}

    def _refresh_candidates(self) -> list[AntigravityProfileCandidate]:
        candidates = antigravity_discovery.discover_profiles()
        self._candidates_by_id = {_candidate_key(c): c for c in candidates}
        return candidates

    def discover_profiles(self) -> list[ProfileStatus]:
        profiles: list[ProfileStatus] = []
        for c in self._refresh_candidates():
            profile_id = _candidate_key(c)
            profiles.append(
                ProfileStatus(
                    provider=self.provider_name,
                    profile_id=profile_id,
                    profile_key=f"{self.provider_name}:{profile_id}",
                    label=c.label,
                    sanitized_source=sanitize_path(str(c.config_home)),
                    discovery_source=c.source,
                    is_active=True,
                    executable_found=c.executable is not None,
                )
            )
        return profiles

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        if not self._candidates_by_id:
            self._refresh_candidates()
        c = self._candidates_by_id.get(profile.profile_id)
        if c is None:
            return False, "profile no longer discoverable"
        credible = antigravity_discovery.credible_home(c.config_home)
        return credible, "credible home" if credible else "home directory missing signals"

    def fetch_usage(self, profile: ProfileStatus) -> dict[str, Any]:
        if not self._candidates_by_id:
            self._refresh_candidates()
        candidate = self._candidates_by_id.get(profile.profile_id)
        if candidate is None:
            return {"ok": False, "error": "profile no longer discoverable"}
        snapshot_result = read_usage_snapshot()
        if snapshot_result is not None:
            return {
                "ok": snapshot_result.ok and bool(snapshot_result.windows),
                "error": snapshot_result.reason,
                "windows": snapshot_result.windows,
                "usage_command": snapshot_result,
                "source": "antigravity_usage_snapshot",
            }
        if not self._usage_command_enabled():
            return {
                "ok": False,
                "error": (
                    "Antigravity has an interactive `/usage` command, but `agy --print /usage` "
                    "does not execute that slash command; automatic probing is disabled to avoid "
                    "creating Antigravity turns. Put copied `/usage` panel text in "
                    f"{_display_snapshot_path()} to monitor it safely."
                ),
            }
        if candidate.executable is None:
            return {"ok": False, "error": "agy executable not found"}
        command_result = self._run_usage_command(candidate)
        return {
            "ok": command_result.ok and bool(command_result.windows),
            "error": command_result.reason,
            "windows": command_result.windows,
            "usage_command": command_result,
            "source": "antigravity_usage_command",
        }

    def _usage_command_enabled(self) -> bool:
        return os.environ.get("CCM_ANTIGRAVITY_USAGE_COMMAND", "0") == "1"

    def _run_usage_command(
        self, candidate: AntigravityProfileCandidate
    ) -> AntigravityUsageCommandResult:
        return run_usage_command(candidate)

    def parse_usage(self, profile: ProfileStatus, raw: dict[str, Any]) -> list[UsageLimit]:
        now = datetime.now(UTC)
        usage_command: AntigravityUsageCommandResult | None = raw.get("usage_command")
        if not raw.get("ok"):
            reason = str(raw.get("error") or "Antigravity usage unavailable.")[:300]
            return [
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason=reason,
                    observed_at_utc=now,
                    source_detail={
                        "source": raw.get("source") or "antigravity_usage_command",
                        "usage_command_ok": usage_command.ok if usage_command else None,
                        "usage_command_reason": usage_command.reason if usage_command else None,
                    },
                )
            ]

        return [
            UsageLimit(
                provider=self.provider_name,
                profile_id=profile.profile_id,
                window_id=window.window_name,
                window_label=window.window_label,
                used_percent=window.used_percentage,
                remaining_percent=max(0.0, 100.0 - window.used_percentage),
                reset_confirmed=False,
                quality=DataQuality.VERIFIED,
                observed_at_utc=datetime.fromtimestamp(window.updated_utc, tz=UTC),
                source_detail={
                    "source": raw.get("source") or "antigravity_usage_command",
                    "command": (
                        "agy -p /usage --output-format json"
                        if raw.get("source") != "antigravity_usage_snapshot"
                        else "usage snapshot text file"
                    ),
                },
            )
            for window in raw.get("windows", [])
        ]

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        return {}

    def diagnose_error(self, profile: ProfileStatus, error: Exception | str) -> ProfileDiagnostics:
        candidate = self._candidates_by_id.get(profile.profile_id)
        exe_sanitized = None
        if candidate and candidate.executable:
            exe_sanitized = sanitize_path(str(candidate.executable))
        return ProfileDiagnostics(
            provider=self.provider_name,
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            last_command_result=None,
            parser_used="antigravity_usage_command",
            current_error=str(error)[:300] if error else None,
            suggested_action=(
                "Open Antigravity CLI and run `/usage`. `agy --print /usage` is not used by default "
                "because it creates a normal Antigravity turn instead of opening the slash-command panel. "
                f"Put copied panel text in {_display_snapshot_path()} to monitor it safely."
            ),
            executable_path_sanitized=exe_sanitized,
        )


def _display_snapshot_path() -> str:
    return sanitize_path(str(usage_snapshot_path()))
