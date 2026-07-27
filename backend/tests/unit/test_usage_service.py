from __future__ import annotations

from datetime import UTC, datetime, timedelta

from claude_codex_monitor.models.usage import DataQuality, UsageLimit
from claude_codex_monitor.services.history_service import HistoryService
from claude_codex_monitor.services.usage_service import UsageService


def _limit(
    *,
    window_id: str,
    window_label: str,
    quality: DataQuality,
    observed_at_utc: datetime,
    used_percent: float | None = None,
    unavailable_reason: str | None = None,
) -> UsageLimit:
    remaining_percent = None if used_percent is None else 100.0 - used_percent
    return UsageLimit(
        provider="codex",
        profile_id="c:\\users\\getra\\.codex",
        window_id=window_id,
        window_label=window_label,
        used_percent=used_percent,
        remaining_percent=remaining_percent,
        quality=quality,
        unavailable_reason=unavailable_reason,
        observed_at_utc=observed_at_utc,
    )


def test_current_limits_use_latest_refresh_batch(store):
    history = HistoryService(store)
    service = UsageService(store, None, history, None, None)  # type: ignore[arg-type]
    profile_key = "codex:c:\\users\\getra\\.codex"
    old = datetime(2026, 7, 27, 9, 16, tzinfo=UTC)
    new = old + timedelta(hours=7)

    history.record(
        profile_key,
        _limit(
            window_id="unknown",
            window_label="Usage",
            quality=DataQuality.UNAVAILABLE,
            unavailable_reason="app-server timeout waiting for account/rateLimits/read",
            observed_at_utc=old,
        ),
    )
    history.record(
        profile_key,
        _limit(
            window_id="primary",
            window_label="Primary",
            quality=DataQuality.VERIFIED,
            used_percent=25.0,
            observed_at_utc=new,
        ),
    )

    limits = service.get_current_limits(profile_key)

    assert [limit.window_id for limit in limits] == ["primary"]
    assert limits[0].used_percent == 25.0


def test_current_limits_normalizes_old_codex_duration_labels(store):
    history = HistoryService(store)
    service = UsageService(store, None, history, None, None)  # type: ignore[arg-type]
    profile_key = "codex:c:\\users\\getra\\.codex"

    history.record(
        profile_key,
        _limit(
            window_id="primary",
            window_label="1 week",
            quality=DataQuality.VERIFIED,
            used_percent=27.0,
            observed_at_utc=datetime(2026, 7, 27, 16, 57, tzinfo=UTC),
        ),
    )

    limits = service.get_current_limits(profile_key)

    assert limits[0].window_label == "7-day"
