from __future__ import annotations

from datetime import UTC, datetime

from claude_codex_monitor.models.diagnostics import ProfileDiagnostics
from claude_codex_monitor.services.diagnostics_service import DiagnosticsService


class _Adapter:
    provider_name = "claude"

    def diagnose_error(self, profile, error):
        return ProfileDiagnostics(
            provider=profile.provider,
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            parser_used="claude_usage_notifier_state_reader",
            current_error=str(error) if error else None,
            suggested_action="Ensure claude-usage-notifier is installed.",
            notifier_db_available=True,
        )


class _Discovery:
    adapters = {"claude": _Adapter()}


def test_diagnostics_reports_latest_snapshot_source(store):
    profile_key = store.upsert_profile(
        provider="claude",
        profile_id="pid",
        label="default",
        sanitized_source="~/.claude",
        discovery_source="default",
        now=datetime(2026, 7, 29, 18, 0, tzinfo=UTC),
    )
    observed = datetime(2026, 7, 29, 18, 46, tzinfo=UTC)
    store.set_profile_refresh_result(profile_key, success=True, now=observed)
    store.insert_snapshot(
        profile_key=profile_key,
        window_id="five_hour",
        window_label="5-hour",
        used_percent=68.0,
        remaining_percent=32.0,
        resets_at_utc=None,
        reset_confirmed=False,
        quality="verified",
        unavailable_reason=None,
        observed_at_utc=observed,
        source_detail={
            "source": "claude_usage_command",
            "command": "claude -p /usage --output-format json",
        },
    )

    diag = DiagnosticsService(store, _Discovery()).diagnose(profile_key)

    assert diag is not None
    assert diag.parser_used == "claude_usage_command"
    assert diag.last_command_result == "Claude `/usage` live command parsed current limit windows."
    assert diag.suggested_action == (
        "Claude `/usage` live command returned parseable limit data for this profile."
    )
