"""Static process configuration (env-derived, not user Settings).

User-editable preferences (theme, retention, refresh interval, etc.) live in
the SQLite `settings` table via services/settings_service.py - this module is
only for things resolved once at process start.
"""

from __future__ import annotations

import os


def port() -> int:
    raw = os.environ.get("CCM_PORT", "8787")
    try:
        return int(raw)
    except ValueError:
        return 8787


def default_refresh_interval_seconds() -> int:
    raw = os.environ.get("CCM_REFRESH_INTERVAL_SECONDS", "300")
    try:
        return max(30, int(raw))
    except ValueError:
        return 300


def default_display_timezone() -> str:
    return os.environ.get("CCM_DISPLAY_TZ", "Asia/Dhaka")


def fake_adapters_enabled() -> bool:
    """Test-only escape hatch: never touches real ~/.claude, ~/.codex or spawns codex.exe."""
    return os.environ.get("CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS") == "1"
