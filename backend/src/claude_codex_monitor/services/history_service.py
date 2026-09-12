"""History persistence, reset-cycle detection and retention sweeps."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ..db.store import Store
from ..models.usage import DataQuality, UsageLimit

LOGGER = logging.getLogger("claude_codex_monitor.services.history")

_RETENTION_SWEEP_MIN_INTERVAL = timedelta(hours=24)
_last_sweep_at: datetime | None = None


class HistoryService:
    def __init__(self, store: Store) -> None:
        self._store = store

    def record(self, profile_key: str, limit: UsageLimit) -> None:
        """Insert a snapshot, detecting reset-cycle boundaries.

        A reset boundary is marked when either:
          - resets_at_utc advanced past the previous reading's resets_at_utc, or
          - used_percent dropped meaningfully (>1pt) from the previous reading
            while quality is verified/derived (never treat this as negative
            consumption - it's a reset, so we mark the boundary instead of
            recording a "decrease").
        """
        previous = self._store.get_last_snapshot(profile_key, limit.window_id)
        is_boundary = False
        if previous is not None:
            prev_pct = previous.get("used_percent")
            prev_reset = previous.get("resets_at_utc")
            prev_reset_dt = _parse(prev_reset) if prev_reset else None
            if (
                limit.resets_at_utc is not None
                and prev_reset_dt is not None
                and limit.resets_at_utc > prev_reset_dt
            ):
                is_boundary = True
            elif (
                limit.used_percent is not None
                and prev_pct is not None
                and limit.used_percent < prev_pct - 1.0
                and limit.quality in (DataQuality.VERIFIED, DataQuality.DERIVED)
            ):
                is_boundary = True

        self._store.insert_snapshot(
            profile_key=profile_key,
            window_id=limit.window_id,
            window_label=limit.window_label,
            used_percent=limit.used_percent,
            used_units=limit.used_units,
            max_units=limit.max_units,
            remaining_percent=limit.remaining_percent,
            resets_at_utc=limit.resets_at_utc,
            reset_confirmed=limit.reset_confirmed,
            quality=limit.quality.value,
            unavailable_reason=limit.unavailable_reason,
            observed_at_utc=limit.observed_at_utc,
            source_detail=limit.source_detail,
            is_reset_boundary=is_boundary,
        )

    def query(
        self,
        *,
        provider: str | None = None,
        profile_key: str | None = None,
        window_id: str | None = None,
        range_key: str = "7d",
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        since = _range_to_since(range_key)
        return self._store.get_history(
            provider=provider,
            profile_key=profile_key,
            window_id=window_id,
            since_utc=since,
            limit=limit,
        )

    def maybe_apply_retention(self, retention_days: int) -> int:
        """Runs at most once per 24h process-wide, always logs before deleting."""
        global _last_sweep_at
        now = datetime.now(UTC)
        if _last_sweep_at is not None and now - _last_sweep_at < _RETENTION_SWEEP_MIN_INTERVAL:
            return 0
        _last_sweep_at = now
        deleted = self._store.apply_retention(retention_days, now=now)
        if deleted:
            LOGGER.info("Retention sweep deleted %d snapshot(s) older than %dd", deleted, retention_days)
        return deleted

    def delete_all(self, confirmed: bool) -> int:
        return self._store.delete_all_history(confirmed=confirmed)


def _range_to_since(range_key: str) -> datetime | None:
    now = datetime.now(UTC)
    mapping = {
        "today": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None,
    }
    delta = mapping.get(range_key, timedelta(days=7))
    return now - delta if delta else None


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
