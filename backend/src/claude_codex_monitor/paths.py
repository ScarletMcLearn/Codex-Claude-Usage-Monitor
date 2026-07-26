"""Absolute path resolution for this app's own data.

Nothing here depends on the current working directory: the backend can be
launched from any directory (pixi run, uvicorn directly, the PowerShell
launcher, or a test runner).
"""

from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """Per-user writable directory for this app's DB, logs and settings.

    Overridable with CCM_DATA_DIR (tests and power users only).
    """
    override = os.environ.get("CCM_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base).resolve() / "ClaudeCodexMonitor"


def history_db_path() -> Path:
    return data_dir() / "history.sqlite3"


def log_dir() -> Path:
    return data_dir() / "logs"


def ensure_dirs() -> None:
    for path in (data_dir(), log_dir()):
        path.mkdir(parents=True, exist_ok=True)


# --- Read-only awareness of the sibling reference projects' own data dirs ---


def claude_usage_notifier_db_path() -> Path:
    """Real state DB of the sibling claude-usage-notifier project, if installed.

    Read-only in principle; we may write back a narrow reset_confirmed flag.
    Never assume this exists - callers must check .exists().
    """
    override = os.environ.get("CLAUDE_USAGE_NOTIFIER_HOME")
    if override:
        base = Path(override).expanduser().resolve()
    else:
        base = Path(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")).resolve() / (
            "ClaudeUsageNotifier"
        )
    return base / "state" / "usage_state.sqlite3"
