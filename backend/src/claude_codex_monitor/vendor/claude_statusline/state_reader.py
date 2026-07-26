# Adapted from I:\Projects\Automation\Claude\Notifications\claude-usage-notifier
# state_store.py (not imported at runtime; copied and modified for this project).
"""Read (and narrowly write-back) the sibling claude-usage-notifier's real
SQLite state DB, if that separate tool happens to be installed on this
machine, capturing statusline rate-limit observations.

This dashboard never fabricates data: if the sibling DB does not exist, or
has no rows for a given profile, callers must treat that profile's Claude
usage as unavailable with a clear reason - never a fabricated 0%/100%.

Schema (matches the sibling project's tables `profiles` and `windows`):
    profiles(profile_id PK, label, config_dir, last_seen_utc, claude_version, last_session)
    windows(profile_id, window_name, used_percentage, resets_at, updated_utc,
            prev_percentage, prev_resets_at, reset_confirmed, PK(profile_id,window_name))
"""

from __future__ import annotations

import dataclasses
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

_BUSY_TIMEOUT_MS = 4000


@dataclasses.dataclass
class WindowReading:
    profile_id: str
    window_name: str
    used_percentage: float | None
    resets_at: int | None
    updated_utc: float
    prev_percentage: float | None
    prev_resets_at: int | None
    reset_confirmed: bool

    @property
    def resets_at_utc(self) -> datetime | None:
        if self.resets_at is None:
            return None
        return datetime.fromtimestamp(self.resets_at, tz=timezone.utc)

    @property
    def updated_at_utc(self) -> datetime:
        return datetime.fromtimestamp(self.updated_utc, tz=timezone.utc)


class ClaudeNotifierStateReader:
    """Read-only (plus limited reset_confirmed write-back) access to the
    sibling notifier's DB. Safe to instantiate even when the DB is absent -
    all methods degrade gracefully rather than raising.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def is_available(self) -> bool:
        return self.path.exists()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection | None]:
        if not self.path.exists():
            yield None
            return
        connection = sqlite3.connect(
            f"file:{self.path}?mode=ro",
            uri=True,
            timeout=_BUSY_TIMEOUT_MS / 1000.0,
        )
        try:
            connection.row_factory = sqlite3.Row
            yield connection
        except sqlite3.DatabaseError:
            yield None
        finally:
            connection.close()

    def get_windows_for_profile(self, profile_id: str) -> list[WindowReading]:
        with self._connect() as connection:
            if connection is None:
                return []
            try:
                rows = connection.execute(
                    "SELECT profile_id, window_name, used_percentage, resets_at, updated_utc, "
                    "prev_percentage, prev_resets_at, reset_confirmed FROM windows "
                    "WHERE profile_id = ?",
                    (profile_id,),
                ).fetchall()
            except sqlite3.DatabaseError:
                return []
        return [
            WindowReading(
                profile_id=row["profile_id"],
                window_name=row["window_name"],
                used_percentage=row["used_percentage"],
                resets_at=row["resets_at"],
                updated_utc=row["updated_utc"],
                prev_percentage=row["prev_percentage"],
                prev_resets_at=row["prev_resets_at"],
                reset_confirmed=bool(row["reset_confirmed"]),
            )
            for row in rows
        ]

    def mark_reset_confirmed_seen(self, profile_id: str, window_name: str) -> bool:
        """Best-effort write-back to clear a reset_confirmed flag once this
        dashboard has recorded the new cycle. Returns False silently on any
        failure (read-only filesystem, locked DB, DB absent, etc.) - this is
        a courtesy write, never load-bearing.
        """
        if not self.path.exists():
            return False
        try:
            connection = sqlite3.connect(str(self.path), timeout=_BUSY_TIMEOUT_MS / 1000.0)
            try:
                connection.execute(
                    "UPDATE windows SET reset_confirmed = 0 WHERE profile_id = ? AND window_name = ?",
                    (profile_id, window_name),
                )
                connection.commit()
            finally:
                connection.close()
            return True
        except sqlite3.DatabaseError:
            return False
