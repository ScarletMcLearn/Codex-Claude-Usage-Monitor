"""Claude Code provider adapter.

Discovery is fully self-contained (vendor/claude_statusline/discovery.py).
Usage data comes from reading the sibling claude-usage-notifier's real
state DB at %LOCALAPPDATA%\\ClaudeUsageNotifier\\ if that separate tool is
installed and has captured statusline data for a profile. If that DB or
profile row doesn't exist, usage is reported UNAVAILABLE with a clear
reason - never fabricated.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus, sanitize_path
from ..models.usage import DataQuality, UsageLimit
from ..paths import claude_usage_notifier_db_path
from ..vendor.claude_statusline import discovery as claude_discovery
from ..vendor.claude_statusline.models import WINDOW_LABELS
from ..vendor.claude_statusline.state_reader import ClaudeNotifierStateReader
from ..vendor.claude_usage_command import ClaudeUsageCommandResult, run_usage_command

LOGGER = logging.getLogger("claude_codex_monitor.adapters.claude")

# Claude values are snapshots from the statusline hook, not a live query the
# dashboard can force. Keep the freshness window short so fast-moving limit
# usage is not shown as "verified" long after Claude last emitted statusline
# data.
_STALE_AFTER_SECONDS = 10 * 60


class ClaudeProviderAdapter:
    provider_name = "claude"

    def __init__(self, notifier_db_path=None) -> None:
        self._notifier_db_path = notifier_db_path or claude_usage_notifier_db_path()

    def discover_profiles(self) -> list[ProfileStatus]:
        candidates = claude_discovery.discover_profiles()
        profiles: list[ProfileStatus] = []
        for c in candidates:
            profile_id = c.profile_id
            profiles.append(
                ProfileStatus(
                    provider=self.provider_name,
                    profile_id=profile_id,
                    profile_key=f"{self.provider_name}:{profile_id}",
                    label=c.label,
                    sanitized_source=sanitize_path(str(c.config_dir)),
                    discovery_source=c.source,
                    is_active=True,
                    executable_found=c.claude_executable is not None,
                )
            )
        return profiles

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        # Re-run discovery cheaply and check presence; discovery already
        # validated credibility so this is mostly a liveness re-check.
        candidates = {c.profile_id: c for c in claude_discovery.discover_profiles()}
        c = candidates.get(profile.profile_id)
        if c is None:
            return False, "profile no longer discoverable"
        return c.valid, c.reason

    def _reader(self) -> ClaudeNotifierStateReader:
        return ClaudeNotifierStateReader(self._notifier_db_path)

    def _usage_command_enabled(self) -> bool:
        return os.environ.get("CCM_CLAUDE_USAGE_COMMAND", "1") != "0"

    def _run_usage_command(self, profile: ProfileStatus) -> ClaudeUsageCommandResult:
        return run_usage_command(profile.profile_id)

    def fetch_usage(self, profile: ProfileStatus) -> dict[str, Any]:
        """Best available Claude lookup. Never raises.

        Prefer the user's own `/usage` command path when it yields explicit
        rate-limit percentages; otherwise fall back to the statusline DB.
        """
        command_result = None
        if self._usage_command_enabled():
            command_result = self._run_usage_command(profile)
            if command_result.ok and command_result.windows:
                return {
                    "ok": True,
                    "reason": None,
                    "windows": command_result.windows,
                    "source": "claude_usage_command",
                    "usage_command": command_result,
                }

        reader = self._reader()
        if not reader.is_available():
            return {
                "ok": False,
                "reason": (
                    "Claude usage notifier database not found at the expected location. "
                    "Install/run the separate claude-usage-notifier tool with its "
                    "statusline hook configured to populate real usage data."
                ),
                "windows": [],
                "source": "claude_usage_notifier_db",
                "usage_command": command_result,
            }
        windows = reader.get_windows_for_profile(profile.profile_id)
        if not windows:
            return {
                "ok": False,
                "reason": (
                    "Claude usage notifier has not captured any statusline data yet "
                    "for this profile (rate limits only appear for Pro/Max accounts "
                    "after the first API response in a session)."
                ),
                "windows": [],
                "source": "claude_usage_notifier_db",
                "usage_command": command_result,
            }
        return {
            "ok": True,
            "reason": None,
            "windows": windows,
            "source": "claude_usage_notifier_db",
            "usage_command": command_result,
        }

    def parse_usage(self, profile: ProfileStatus, raw: dict[str, Any]) -> list[UsageLimit]:
        now = datetime.now(UTC)
        if not raw.get("ok"):
            # Report a single UNAVAILABLE placeholder row (window_id "unknown")
            # so the UI has something to render per profile even with zero data.
            return [
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason=raw.get("reason") or "No data available",
                    observed_at_utc=now,
                )
            ]

        source = raw.get("source") or "claude_usage_notifier_db"
        usage_command: ClaudeUsageCommandResult | None = raw.get("usage_command")
        results: list[UsageLimit] = []
        reading: Any
        for reading in raw["windows"]:
            if source == "claude_usage_command":
                used_percent = reading.used_percentage
                results.append(
                    UsageLimit(
                        provider=self.provider_name,
                        profile_id=profile.profile_id,
                        window_id=reading.window_name,
                        window_label=WINDOW_LABELS.get(reading.window_name) or reading.window_name,
                        used_percent=used_percent,
                        remaining_percent=max(0.0, 100.0 - used_percent),
                        resets_at_utc=reading.resets_at_utc,
                        reset_confirmed=False,
                        quality=DataQuality.VERIFIED,
                        observed_at_utc=datetime.fromtimestamp(reading.updated_utc, tz=UTC),
                        source_detail={
                            "source": "claude_usage_command",
                            "command": "claude -p /usage --output-format json",
                        },
                    )
                )
                continue

            age_seconds = time.time() - reading.updated_utc
            quality = DataQuality.VERIFIED
            reason = None
            if age_seconds > _STALE_AFTER_SECONDS:
                quality = DataQuality.STALE
                age_minutes = max(1, int(age_seconds // 60))
                if age_minutes >= 60:
                    age_text = f"{age_minutes // 60}h ago"
                else:
                    age_text = f"{age_minutes}m ago"
                reason = (
                    f"Last observed {age_text}; Claude statusline has not reported newer data."
                )

            used_percent = reading.used_percentage
            remaining_percent = None
            if used_percent is not None:
                remaining_percent = max(0.0, 100.0 - used_percent)

            results.append(
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id=reading.window_name,
                    window_label=WINDOW_LABELS.get(reading.window_name) or reading.window_name,
                    used_percent=used_percent,
                    remaining_percent=remaining_percent,
                    resets_at_utc=reading.resets_at_utc,
                    reset_confirmed=reading.reset_confirmed,
                    quality=quality,
                    unavailable_reason=reason,
                    observed_at_utc=reading.updated_at_utc,
                    source_detail={
                        "prev_percentage": reading.prev_percentage,
                        "prev_resets_at": reading.prev_resets_at,
                        "source": "claude_usage_notifier_db",
                        "usage_command_ok": usage_command.ok if usage_command else None,
                        "usage_command_reason": usage_command.reason if usage_command else None,
                    },
                )
            )
        return results

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        # No non-secret account metadata reliably available from the notifier
        # DB today (it only stores rate-limit windows, not plan/email).
        return {}

    def diagnose_error(self, profile: ProfileStatus, error: Exception | str) -> ProfileDiagnostics:
        reader = self._reader()
        return ProfileDiagnostics(
            provider=self.provider_name,
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            last_command_result=None,
            parser_used="claude_usage_notifier_state_reader",
            current_error=str(error)[:300] if error else None,
            suggested_action=(
                "Ensure claude-usage-notifier is installed and its statusline hook is "
                "configured for this profile, and that you've had at least one Claude "
                "Code session with an API response since the last reset."
            ),
            executable_path_sanitized=(
                sanitize_path(profile.sanitized_source) if profile.sanitized_source else None
            ),
            notifier_db_available=reader.is_available(),
            notifier_db_reason=None if reader.is_available() else "notifier state DB not found",
        )
