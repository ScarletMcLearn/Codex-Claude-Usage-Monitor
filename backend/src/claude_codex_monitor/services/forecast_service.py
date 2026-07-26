"""Simple linear-extrapolation forecasting. Always ESTIMATED, never merged
into the real used_percent field. Only computed when there is enough
history in the *current* reset cycle.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..db.store import Store
from ..models.usage import DataQuality, ForecastResult

_MIN_SNAPSHOTS = 3


class ForecastService:
    def __init__(self, store: Store) -> None:
        self._store = store

    def forecast(self, provider: str, profile_key: str, window_id: str) -> ForecastResult:
        rows = self._store.get_history(
            provider=provider, profile_key=profile_key, window_id=window_id, limit=500
        )
        # Only consider snapshots since the most recent reset boundary.
        boundary_index = -1
        for i, row in enumerate(rows):
            if row.get("is_reset_boundary"):
                boundary_index = i
        current_cycle = rows[boundary_index + 1 :] if boundary_index >= 0 else rows

        usable = [
            r
            for r in current_cycle
            if r.get("used_percent") is not None
            and r.get("quality") in (DataQuality.VERIFIED.value, DataQuality.DERIVED.value)
        ]

        if len(usable) < _MIN_SNAPSHOTS:
            return ForecastResult(
                provider=provider,
                profile_id=profile_key,
                window_id=window_id,
                has_enough_data=False,
                basis_snapshot_count=len(usable),
                reason=f"Need at least {_MIN_SNAPSHOTS} verified readings in the current cycle "
                f"(have {len(usable)}).",
            )

        first, last = usable[0], usable[-1]
        t0 = _parse(first["observed_at_utc"])
        t1 = _parse(last["observed_at_utc"])
        if t0 is None or t1 is None or t1 <= t0:
            return ForecastResult(
                provider=provider,
                profile_id=profile_key,
                window_id=window_id,
                has_enough_data=False,
                basis_snapshot_count=len(usable),
                reason="Insufficient time spread between readings to compute a rate.",
            )

        hours = (t1 - t0).total_seconds() / 3600.0
        delta_pct = last["used_percent"] - first["used_percent"]
        if delta_pct <= 0 or hours <= 0:
            return ForecastResult(
                provider=provider,
                profile_id=profile_key,
                window_id=window_id,
                has_enough_data=False,
                basis_snapshot_count=len(usable),
                reason="Usage is flat or decreasing in the current cycle; no exhaustion to project.",
            )

        rate_per_hour = delta_pct / hours
        remaining_pct = max(0.0, 100.0 - last["used_percent"])
        hours_to_exhaustion = remaining_pct / rate_per_hour if rate_per_hour > 0 else None
        projected = None
        if hours_to_exhaustion is not None:
            from datetime import timedelta

            projected = t1 + timedelta(hours=hours_to_exhaustion)

        return ForecastResult(
            provider=provider,
            profile_id=profile_key,
            window_id=window_id,
            has_enough_data=True,
            projected_exhaustion_at_utc=projected,
            rate_percent_per_hour=rate_per_hour,
            basis_snapshot_count=len(usable),
            quality=DataQuality.ESTIMATED,
        )


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
