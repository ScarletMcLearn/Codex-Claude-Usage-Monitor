# Adapted from I:\Projects\Automation\Claude\Notifications\claude-usage-notifier
# (not imported at runtime; copied and modified for this project).
"""Data models for the Claude Code status-line rate-limit contract.

Verified against Claude Code 2.1.219+ and https://code.claude.com/docs/en/statusline:

    rate_limits.five_hour.used_percentage    float 0..100
    rate_limits.five_hour.resets_at          Unix epoch SECONDS
    rate_limits.seven_day.used_percentage    float 0..100
    rate_limits.seven_day.resets_at          Unix epoch SECONDS

``rate_limits`` appears only for Claude.ai subscribers (Pro/Max) and only
after the first API response in a session. A window may be independently
absent - that must render as "no data", never zero.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

WINDOW_FIVE_HOUR = "five_hour"
WINDOW_SEVEN_DAY = "seven_day"
KNOWN_WINDOWS = (WINDOW_FIVE_HOUR, WINDOW_SEVEN_DAY)

WINDOW_LABELS = {
    WINDOW_FIVE_HOUR: "5-hour",
    WINDOW_SEVEN_DAY: "7-day",
}

_MIN_EPOCH = 1_577_836_800
_MAX_EPOCH = 4_102_444_800


def coerce_percentage(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    if pct != pct or pct in (float("inf"), float("-inf")):
        return None
    return max(0.0, min(100.0, pct))


def coerce_epoch_seconds(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        epoch = float(value)
    except (TypeError, ValueError):
        return None
    if epoch != epoch or epoch in (float("inf"), float("-inf")):
        return None
    if epoch > _MAX_EPOCH and (epoch / 1000.0) <= _MAX_EPOCH:
        epoch = epoch / 1000.0
    epoch_int = int(epoch)
    if epoch_int < _MIN_EPOCH or epoch_int > _MAX_EPOCH:
        return None
    return epoch_int


def epoch_to_utc(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


@dataclasses.dataclass(frozen=True)
class WindowSnapshot:
    name: str
    used_percentage: float | None
    resets_at: int | None

    @property
    def resets_at_utc(self) -> datetime | None:
        return epoch_to_utc(self.resets_at) if self.resets_at is not None else None


@dataclasses.dataclass(frozen=True)
class StatusLinePayload:
    """Deliberately narrow: never retains prompts, transcripts or credentials."""

    session_id: str | None
    version: str | None
    windows: dict[str, WindowSnapshot]
    had_rate_limits: bool

    @classmethod
    def parse(cls, raw: Any) -> "StatusLinePayload":
        if not isinstance(raw, dict):
            return cls(session_id=None, version=None, windows={}, had_rate_limits=False)

        session_id = raw.get("session_id")
        session_id = session_id if isinstance(session_id, str) and session_id else None

        version = raw.get("version")
        version = version if isinstance(version, str) and version else None

        rate_limits = raw.get("rate_limits")
        had_rate_limits = isinstance(rate_limits, dict)

        windows: dict[str, WindowSnapshot] = {}
        if had_rate_limits:
            for name in KNOWN_WINDOWS:
                block = rate_limits.get(name)
                if not isinstance(block, dict):
                    continue
                pct = coerce_percentage(block.get("used_percentage"))
                resets_at = coerce_epoch_seconds(block.get("resets_at"))
                if pct is None and resets_at is None:
                    continue
                windows[name] = WindowSnapshot(name=name, used_percentage=pct, resets_at=resets_at)

        return cls(
            session_id=session_id, version=version, windows=windows, had_rate_limits=had_rate_limits
        )
