"""Shared usage-limit domain model.

The DataQuality enum is the single source of truth for how honest a metric
is. Never present a value at a higher quality than the data supports, and
never fabricate max_units / a denominator that wasn't actually observed.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DataQuality(str, Enum):
    VERIFIED = "verified"      # read directly from an authoritative live source this refresh
    DERIVED = "derived"        # computed from verified data (e.g. remaining = 100 - used)
    ESTIMATED = "estimated"    # forecast/extrapolation - never real, always labeled
    STALE = "stale"            # last known reading, but source unreachable/too old now
    UNAVAILABLE = "unavailable"  # no data ever obtained; must show reason


class UsageLevel(str, Enum):
    """Bucketed severity for usage bars - always paired with text+icon, not color alone."""

    NORMAL = "normal"          # < 50%
    MODERATE = "moderate"      # 50-79%
    HIGH = "high"              # 80-94%
    CRITICAL = "critical"      # 95-99%
    EXHAUSTED = "exhausted"    # >= 100%
    UNKNOWN = "unknown"        # quality is unavailable/stale-without-value


def level_for_percent(used_percent: float | None, quality: DataQuality) -> UsageLevel:
    if used_percent is None or quality == DataQuality.UNAVAILABLE:
        return UsageLevel.UNKNOWN
    if used_percent >= 100:
        return UsageLevel.EXHAUSTED
    if used_percent >= 95:
        return UsageLevel.CRITICAL
    if used_percent >= 80:
        return UsageLevel.HIGH
    if used_percent >= 50:
        return UsageLevel.MODERATE
    return UsageLevel.NORMAL


class UsageLimit(BaseModel):
    """One rate-limit window observation, provider-agnostic."""

    provider: str  # "claude" | "codex"
    profile_id: str
    window_id: str  # five_hour/seven_day (claude) or primary/secondary (codex)
    window_label: str
    window_duration_minutes: int | None = None

    used_percent: float | None = None
    used_units: float | None = None  # always None today - no provider exposes raw units
    max_units: float | None = None  # always None today - NEVER invent a denominator
    remaining_percent: float | None = None  # only set when used_percent is verified/derived

    resets_at_utc: datetime | None = None
    reset_confirmed: bool = False

    quality: DataQuality
    unavailable_reason: str | None = None
    observed_at_utc: datetime

    source_detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def level(self) -> UsageLevel:
        return level_for_percent(self.used_percent, self.quality)


class ForecastResult(BaseModel):
    """Always ESTIMATED. Never merged into the "real" used_percent field."""

    provider: str
    profile_id: str
    window_id: str
    has_enough_data: bool
    projected_exhaustion_at_utc: datetime | None = None
    rate_percent_per_hour: float | None = None
    basis_snapshot_count: int = 0
    quality: DataQuality = DataQuality.ESTIMATED
    reason: str | None = None
