"""In-memory fake adapters for e2e/demo use only.

Activated when CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1. Never touches real
~/.claude, ~/.codex, or spawns codex.exe - used by Playwright e2e tests and
local demoing without real credentials.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus
from ..models.usage import DataQuality, UsageLimit


class FakeClaudeAdapter:
    provider_name = "claude"

    def discover_profiles(self) -> list[ProfileStatus]:
        return [
            ProfileStatus(
                provider="claude",
                profile_id="fake-default",
                profile_key="claude:fake-default",
                label="default",
                sanitized_source="~/.claude",
                discovery_source="default",
            ),
            ProfileStatus(
                provider="claude",
                profile_id="fake-work",
                profile_key="claude:fake-work",
                label="work",
                sanitized_source="~/.claude-work",
                discovery_source="ps-profile",
            ),
        ]

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        return True, "fake profile"

    def fetch_usage(self, profile: ProfileStatus) -> Any:
        return {"profile_id": profile.profile_id}

    def parse_usage(self, profile: ProfileStatus, raw: Any) -> list[UsageLimit]:
        now = datetime.now(UTC)
        if profile.profile_id == "fake-work":
            return [
                UsageLimit(
                    provider="claude",
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason="Fake profile: authentication required (demo data).",
                    observed_at_utc=now,
                )
            ]
        return [
            UsageLimit(
                provider="claude",
                profile_id=profile.profile_id,
                window_id="five_hour",
                window_label="5-hour",
                used_percent=42.0,
                remaining_percent=58.0,
                resets_at_utc=now + timedelta(hours=3),
                quality=DataQuality.VERIFIED,
                observed_at_utc=now,
            ),
            UsageLimit(
                provider="claude",
                profile_id=profile.profile_id,
                window_id="seven_day",
                window_label="7-day",
                used_percent=88.0,
                remaining_percent=12.0,
                resets_at_utc=now + timedelta(days=2),
                quality=DataQuality.VERIFIED,
                observed_at_utc=now,
            ),
        ]

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        return {}

    def diagnose_error(self, profile: ProfileStatus, error) -> ProfileDiagnostics:
        return ProfileDiagnostics(
            provider="claude",
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            parser_used="fake_adapter",
            current_error=str(error) if error else None,
            suggested_action="This is fake/demo data (CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1).",
            notifier_db_available=False,
            notifier_db_reason="Fake adapter never reads a real notifier DB.",
        )


class FakeCodexAdapter:
    provider_name = "codex"

    def discover_profiles(self) -> list[ProfileStatus]:
        return [
            ProfileStatus(
                provider="codex",
                profile_id="fake-codex-default",
                profile_key="codex:fake-codex-default",
                label="default",
                sanitized_source="~/.codex",
                discovery_source="default home",
            )
        ]

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        return True, "fake profile"

    def fetch_usage(self, profile: ProfileStatus) -> Any:
        return {"profile_id": profile.profile_id}

    def parse_usage(self, profile: ProfileStatus, raw: Any) -> list[UsageLimit]:
        now = datetime.now(UTC)
        return [
            UsageLimit(
                provider="codex",
                profile_id=profile.profile_id,
                window_id="primary",
                window_label="7-day",
                window_duration_minutes=10080,
                used_percent=15.0,
                remaining_percent=85.0,
                resets_at_utc=now + timedelta(days=5),
                quality=DataQuality.VERIFIED,
                observed_at_utc=now,
            )
        ]

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        return {"account_label": "demo@example.invalid (plus)"}

    def diagnose_error(self, profile: ProfileStatus, error) -> ProfileDiagnostics:
        return ProfileDiagnostics(
            provider="codex",
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            parser_used="fake_adapter",
            current_error=str(error) if error else None,
            suggested_action="This is fake/demo data (CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1).",
        )
