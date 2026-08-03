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


def test_current_limits_keeps_prior_real_rows_when_latest_refresh_is_unknown(store):
    history = HistoryService(store)
    service = UsageService(store, None, history, None, None)  # type: ignore[arg-type]
    profile_key = "codex:c:\\users\\getra\\.codex"
    old = datetime.now(UTC) - timedelta(minutes=20)
    new = datetime.now(UTC)

    history.record(
        profile_key,
        _limit(
            window_id="primary",
            window_label="7-day",
            quality=DataQuality.VERIFIED,
            used_percent=25.0,
            observed_at_utc=old,
        ),
    )
    history.record(
        profile_key,
        _limit(
            window_id="unknown",
            window_label="Usage",
            quality=DataQuality.UNAVAILABLE,
            unavailable_reason="app-server timeout waiting for account/rateLimits/read",
            observed_at_utc=new,
        ),
    )

    limits = service.get_current_limits(profile_key)

    assert [limit.window_id for limit in limits] == ["primary"]
    assert limits[0].used_percent == 25.0
    assert limits[0].quality == DataQuality.STALE
    assert "Last observed" in limits[0].unavailable_reason


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


def test_current_limits_ignores_oldest_history_limit(store):
    history = HistoryService(store)
    service = UsageService(store, None, history, None, None)  # type: ignore[arg-type]
    profile_key = "claude:c:\\users\\getra\\.claude"
    start = datetime(2026, 7, 1, 0, 0, tzinfo=UTC)

    for i in range(1001):
        history.record(
            profile_key,
            _limit(
                window_id="five_hour",
                window_label="5-hour",
                quality=DataQuality.VERIFIED,
                used_percent=78.0,
                observed_at_utc=start + timedelta(minutes=i),
            ),
        )
    history.record(
        profile_key,
        _limit(
            window_id="five_hour",
            window_label="5-hour",
            quality=DataQuality.VERIFIED,
            used_percent=100.0,
            observed_at_utc=start + timedelta(minutes=1002),
        ),
    )

    limits = service.get_current_limits(profile_key)

    assert len(limits) == 1
    assert limits[0].used_percent == 100.0


def test_current_limits_returns_latest_row_per_window(store):
    history = HistoryService(store)
    service = UsageService(store, None, history, None, None)  # type: ignore[arg-type]
    profile_key = "antigravity:c:\\users\\getra\\.gemini\\config\\projects::project:default-cli-project"
    observed = datetime(2026, 7, 27, 16, 57, tzinfo=UTC)

    for percent in (10.0, 42.0, 73.0):
        store.insert_snapshot(
            profile_key=profile_key,
            window_id="gemini_models_weekly_limit",
            window_label="Gemini Models: Weekly Limit",
            used_percent=percent,
            remaining_percent=100.0 - percent,
            resets_at_utc=None,
            reset_confirmed=False,
            quality=DataQuality.VERIFIED.value,
            unavailable_reason=None,
            observed_at_utc=observed,
        )

    limits = service.get_current_limits(profile_key)

    assert len(limits) == 1
    assert limits[0].window_id == "gemini_models_weekly_limit"
    assert limits[0].used_percent == 73.0
