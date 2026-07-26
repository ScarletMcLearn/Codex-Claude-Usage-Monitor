"""Display timezone resolution.

All timestamps are stored internally as UTC. Display timezone defaults to
Asia/Dhaka per spec, configurable in Settings. Windows ships no IANA tz
database, so resolution falls back to a small fixed-offset table for
DST-free zones (adapted approach; not a verbatim copy - see
vendor/claude_statusline/timezones.py for the ported original with full
provenance comment).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo

DEFAULT_DISPLAY_TZ = "Asia/Dhaka"

_FIXED_OFFSETS: dict[str, int] = {
    "utc": 0,
    "etc/utc": 0,
    "asia/dhaka": 6 * 60,
    "asia/kolkata": 5 * 60 + 30,
    "asia/karachi": 5 * 60,
    "asia/kathmandu": 5 * 60 + 45,
    "asia/colombo": 5 * 60 + 30,
    "asia/bangkok": 7 * 60,
    "asia/jakarta": 7 * 60,
    "asia/singapore": 8 * 60,
    "asia/hong_kong": 8 * 60,
    "asia/shanghai": 8 * 60,
    "asia/tokyo": 9 * 60,
    "asia/seoul": 9 * 60,
    "asia/dubai": 4 * 60,
}

_FIXED_NAMES: dict[str, str] = {
    "asia/dhaka": "+06",
    "asia/kolkata": "+0530",
    "asia/tokyo": "+09",
    "asia/singapore": "+08",
    "asia/dubai": "+04",
}


class ResolvedZone:
    __slots__ = ("tz", "name", "source", "warning")

    def __init__(self, tz: tzinfo, name: str, source: str, warning: str | None = None) -> None:
        self.tz = tz
        self.name = name
        self.source = source
        self.warning = warning


def resolve_zone(name: str | None) -> ResolvedZone:
    requested = (name or "").strip() or DEFAULT_DISPLAY_TZ
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            return ResolvedZone(ZoneInfo(requested), requested, "zoneinfo")
        except (ZoneInfoNotFoundError, ValueError, OSError, ModuleNotFoundError):
            pass
    except ImportError:  # pragma: no cover
        pass

    key = requested.lower().replace(" ", "_")
    offset_minutes = _FIXED_OFFSETS.get(key)
    if offset_minutes is not None:
        label = _FIXED_NAMES.get(key) or _format_offset(offset_minutes)
        return ResolvedZone(
            timezone(timedelta(minutes=offset_minutes), label),
            requested,
            "fixed-offset",
            f"No IANA tz database found; using fixed offset {label} for {requested}.",
        )

    return ResolvedZone(
        timezone.utc,
        "UTC",
        "utc-fallback",
        f"Timezone {requested!r} could not be resolved; displaying UTC.",
    )


def _format_offset(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "-"
    total = abs(minutes)
    hours, mins = divmod(total, 60)
    return f"{sign}{hours:02d}" if mins == 0 else f"{sign}{hours:02d}{mins:02d}"


def to_display(dt: datetime | None, tz_name: str | None) -> datetime | None:
    """Convert a UTC-aware datetime to the display timezone. None-safe."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(resolve_zone(tz_name).tz)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
