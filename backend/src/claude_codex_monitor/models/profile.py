"""Profile domain model - normalised view of a discovered Claude or Codex profile."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProfileStatus(BaseModel):
    provider: str  # "claude" | "codex" | "antigravity"
    profile_id: str  # raw internal id (path-derived); never shown raw in UI
    profile_key: str  # "provider:profile_id" - stable cross-table key
    label: str  # user-friendly or auto-derived safe label
    friendly_name: str | None = None  # user-set override, takes precedence for display
    sanitized_source: str  # sanitized/truncated config path or home, safe to display
    discovery_source: str  # e.g. "default", "ps-profile", "home-candidate"
    is_active: bool = True
    is_authenticated: bool | None = None  # None = unknown
    last_refresh_utc: datetime | None = None
    last_success_utc: datetime | None = None
    last_error: str | None = None
    is_stale: bool = False
    executable_found: bool = True


def sanitize_path(raw: str, home_marker: str = "~") -> str:
    """Replace the user home portion of a path with a marker and drop any
    username segment, so config/home paths never leak into the UI/logs.
    """
    import os

    home = os.path.expanduser("~")
    text = str(raw)
    if home and text.lower().startswith(home.lower()):
        text = home_marker + text[len(home):]
    # Defensive: strip any residual "Users\\<name>\\" pattern.
    import re

    text = re.sub(r"([Uu]sers)[\\/][^\\/]+", r"\1\\<user>", text)
    return text
