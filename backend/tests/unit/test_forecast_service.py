from __future__ import annotations

from datetime import UTC, datetime, timedelta

from claude_codex_monitor.models.usage import DataQuality, UsageLimit
from claude_codex_monitor.services.forecast_service import ForecastService
from claude_codex_monitor.services.history_service import HistoryService


def _limit(pct, observed_at):
    return UsageLimit(
        provider="claude",
        profile_id="pid",
        window_id="five_hour",
        window_label="5-hour",
        used_percent=pct,
        quality=DataQuality.VERIFIED,
        observed_at_utc=observed_at,
    )


def test_insufficient_history_reports_not_enough_data(store):
    fc = ForecastService(store)
    result = fc.forecast("claude", "claude:pid", "five_hour")
    assert result.has_enough_data is False
    assert result.quality == DataQuality.ESTIMATED


def test_enough_increasing_history_produces_estimate(store):
    hist = HistoryService(store)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    hist.record("claude:pid", _limit(10, t0))
    hist.record("claude:pid", _limit(20, t0 + timedelta(hours=1)))
    hist.record("claude:pid", _limit(30, t0 + timedelta(hours=2)))

    fc = ForecastService(store)
    result = fc.forecast("claude", "claude:pid", "five_hour")
    assert result.has_enough_data is True
    assert result.quality == DataQuality.ESTIMATED
    assert result.rate_percent_per_hour == 10.0
    assert result.projected_exhaustion_at_utc is not None


def test_flat_usage_reports_no_forecast(store):
    hist = HistoryService(store)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    hist.record("claude:pid", _limit(10, t0))
    hist.record("claude:pid", _limit(10, t0 + timedelta(hours=1)))
    hist.record("claude:pid", _limit(10, t0 + timedelta(hours=2)))

    fc = ForecastService(store)
    result = fc.forecast("claude", "claude:pid", "five_hour")
    assert result.has_enough_data is False
