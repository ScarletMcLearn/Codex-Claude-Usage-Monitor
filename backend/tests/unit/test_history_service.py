from __future__ import annotations

from datetime import UTC, datetime, timedelta

from claude_codex_monitor.models.usage import DataQuality, UsageLimit
from claude_codex_monitor.services.history_service import HistoryService


def _limit(pct, resets_at, observed_at, quality=DataQuality.VERIFIED):
    return UsageLimit(
        provider="claude",
        profile_id="pid",
        window_id="five_hour",
        window_label="5-hour",
        used_percent=pct,
        resets_at_utc=resets_at,
        quality=quality,
        observed_at_utc=observed_at,
    )


def test_increasing_usage_is_not_marked_as_reset_boundary(store):
    svc = HistoryService(store)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    reset = t0 + timedelta(hours=5)
    svc.record("claude:pid", _limit(10, reset, t0))
    svc.record("claude:pid", _limit(20, reset, t0 + timedelta(hours=1)))

    rows = store.get_history(profile_key="claude:pid", limit=10)
    assert rows[-1]["is_reset_boundary"] == 0


def test_usage_drop_is_marked_as_reset_boundary_not_negative_consumption(store):
    svc = HistoryService(store)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    reset = t0 + timedelta(hours=5)
    svc.record("claude:pid", _limit(90, reset, t0))
    # usage drops sharply -> must be a reset, never "negative consumption"
    svc.record("claude:pid", _limit(2, reset, t0 + timedelta(hours=6)))

    rows = store.get_history(profile_key="claude:pid", limit=10)
    assert rows[-1]["is_reset_boundary"] == 1
    assert rows[-1]["used_percent"] == 2  # value stored as-is, just flagged


def test_advanced_reset_timestamp_marks_boundary(store):
    svc = HistoryService(store)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    reset1 = t0 + timedelta(hours=5)
    reset2 = t0 + timedelta(hours=10)
    svc.record("claude:pid", _limit(50, reset1, t0))
    svc.record("claude:pid", _limit(5, reset2, t0 + timedelta(hours=5, minutes=1)))

    rows = store.get_history(profile_key="claude:pid", limit=10)
    assert rows[-1]["is_reset_boundary"] == 1


def test_retention_sweep_logs_before_deleting(store):
    svc = HistoryService(store)
    old = datetime.now(UTC) - timedelta(days=200)
    svc.record("claude:pid", _limit(10, None, old))

    deleted = store.apply_retention(90)
    assert deleted == 1
    log = store.get_refresh_log(limit=5)
    assert any(e["event_type"] == "retention_delete" for e in log)


def test_manual_delete_requires_confirmation(store):
    svc = HistoryService(store)
    svc.record("claude:pid", _limit(10, None, datetime.now(UTC)))
    import pytest

    with pytest.raises(ValueError):
        store.delete_all_history(confirmed=False)
    deleted = svc.delete_all(confirmed=True)
    assert deleted == 1
    log = store.get_refresh_log(limit=5)
    assert any(e["event_type"] == "manual_delete" for e in log)
