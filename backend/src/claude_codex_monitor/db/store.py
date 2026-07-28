"""SQLite store for this app's own data: profiles, history snapshots,
settings KV, refresh/audit log, notification dedupe.

WAL journaling. Retention sweep and manual deletes always write a
refresh_log row before deleting, per the "never silently delete" rule.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..paths import history_db_path
from .schema_loader import SCHEMA_SQL

SCHEMA_VERSION = 1
_BUSY_TIMEOUT_MS = 5000


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else history_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.path, timeout=_BUSY_TIMEOUT_MS / 1000.0, isolation_level=None
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as connection:
            try:
                connection.execute("PRAGMA journal_mode=WAL")
            except sqlite3.DatabaseError:
                pass
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(SCHEMA_SQL)
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                (str(SCHEMA_VERSION),),
            )
            for provider, name in (
                ("claude", "Claude Code"),
                ("codex", "Codex"),
                ("antigravity", "Antigravity"),
            ):
                connection.execute(
                    "INSERT OR IGNORE INTO providers (provider, display_name) VALUES (?, ?)",
                    (provider, name),
                )

    def log_event(
        self, event_type: str, *, profile_key: str | None = None, detail: str | None = None
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO refresh_log (event_utc, event_type, profile_key, detail) VALUES (?, ?, ?, ?)",
                (_iso(datetime.now(UTC)), event_type, profile_key, detail),
            )

    # ------------------------------------------------------------- profiles

    def upsert_profile(
        self,
        *,
        provider: str,
        profile_id: str,
        label: str,
        sanitized_source: str,
        discovery_source: str,
        now: datetime | None = None,
    ) -> str:
        profile_key = f"{provider}:{profile_id}"
        ts = _iso(now or datetime.now(UTC))
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT profile_key FROM profiles WHERE profile_key = ?", (profile_key,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO profiles
                        (profile_key, provider, profile_id, label, sanitized_source,
                         discovery_source, is_active, first_seen_utc, last_seen_utc)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (profile_key, provider, profile_id, label, sanitized_source, discovery_source, ts, ts),
                )
            else:
                connection.execute(
                    """
                    UPDATE profiles SET label = ?, sanitized_source = ?, discovery_source = ?,
                        last_seen_utc = ?
                    WHERE profile_key = ?
                    """,
                    (label, sanitized_source, discovery_source, ts, profile_key),
                )
        return profile_key

    def set_profile_refresh_result(
        self,
        profile_key: str,
        *,
        success: bool,
        error: str | None = None,
        now: datetime | None = None,
    ) -> None:
        ts = _iso(now or datetime.now(UTC))
        with self._connect() as connection:
            if success:
                connection.execute(
                    "UPDATE profiles SET last_refresh_utc = ?, last_success_utc = ?, last_error = NULL "
                    "WHERE profile_key = ?",
                    (ts, ts, profile_key),
                )
            else:
                connection.execute(
                    "UPDATE profiles SET last_refresh_utc = ?, last_error = ? WHERE profile_key = ?",
                    (ts, error, profile_key),
                )

    def set_profile_active(self, profile_key: str, is_active: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE profiles SET is_active = ? WHERE profile_key = ?",
                (1 if is_active else 0, profile_key),
            )

    def set_profile_friendly_name(self, profile_key: str, friendly_name: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE profiles SET friendly_name = ? WHERE profile_key = ?",
                (friendly_name, profile_key),
            )

    def get_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM profiles ORDER BY provider, label").fetchall()
        return [dict(row) for row in rows]

    def get_profile(self, profile_key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE profile_key = ?", (profile_key,)
            ).fetchone()
        return dict(row) if row else None

    # -------------------------------------------------------------- history

    def insert_snapshot(
        self,
        *,
        profile_key: str,
        window_id: str,
        window_label: str | None,
        used_percent: float | None,
        remaining_percent: float | None,
        resets_at_utc: datetime | None,
        reset_confirmed: bool,
        quality: str,
        unavailable_reason: str | None,
        observed_at_utc: datetime,
        source_detail: dict[str, Any] | None = None,
        is_reset_boundary: bool = False,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO usage_snapshots
                    (profile_key, window_id, window_label, used_percent, remaining_percent,
                     resets_at_utc, reset_confirmed, quality, unavailable_reason,
                     observed_at_utc, source_detail_json, is_reset_boundary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_key,
                    window_id,
                    window_label,
                    used_percent,
                    remaining_percent,
                    _iso(resets_at_utc),
                    1 if reset_confirmed else 0,
                    quality,
                    unavailable_reason,
                    _iso(observed_at_utc),
                    json.dumps(source_detail or {}),
                    1 if is_reset_boundary else 0,
                ),
            )
            return cursor.lastrowid or 0

    def get_last_snapshot(self, profile_key: str, window_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM usage_snapshots
                WHERE profile_key = ? AND window_id = ?
                ORDER BY observed_at_utc DESC LIMIT 1
                """,
                (profile_key, window_id),
            ).fetchone()
        return dict(row) if row else None

    def get_history(
        self,
        *,
        provider: str | None = None,
        profile_key: str | None = None,
        window_id: str | None = None,
        since_utc: datetime | None = None,
        until_utc: datetime | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        query = [
            "SELECT s.*, "
            "COALESCE(p.provider, substr(s.profile_key, 1, instr(s.profile_key, ':') - 1)) as provider, "
            "p.label as profile_label, p.friendly_name "
            "FROM usage_snapshots s LEFT JOIN profiles p ON p.profile_key = s.profile_key WHERE 1=1"
        ]
        params: list[Any] = []
        if provider:
            query.append(
                "AND COALESCE(p.provider, substr(s.profile_key, 1, instr(s.profile_key, ':') - 1)) = ?"
            )
            params.append(provider)
        if profile_key:
            query.append("AND s.profile_key = ?")
            params.append(profile_key)
        if window_id:
            query.append("AND s.window_id = ?")
            params.append(window_id)
        if since_utc:
            query.append("AND s.observed_at_utc >= ?")
            params.append(_iso(since_utc))
        if until_utc:
            query.append("AND s.observed_at_utc <= ?")
            params.append(_iso(until_utc))
        query.append("ORDER BY s.observed_at_utc ASC LIMIT ?")
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(" ".join(query), params).fetchall()
        return [dict(row) for row in rows]

    def get_latest_snapshot_batch(self, profile_key: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*,
                    COALESCE(p.provider, substr(s.profile_key, 1, instr(s.profile_key, ':') - 1)) as provider,
                    p.label as profile_label,
                    p.friendly_name
                FROM usage_snapshots s
                LEFT JOIN profiles p ON p.profile_key = s.profile_key
                WHERE s.profile_key = ?
                    AND s.observed_at_utc = (
                        SELECT MAX(s3.observed_at_utc)
                        FROM usage_snapshots s3
                        WHERE s3.profile_key = s.profile_key
                    )
                    AND s.id = (
                        SELECT s2.id
                        FROM usage_snapshots s2
                        WHERE s2.profile_key = s.profile_key
                            AND s2.window_id = s.window_id
                            AND s2.observed_at_utc = s.observed_at_utc
                        ORDER BY s2.observed_at_utc DESC, s2.id DESC
                        LIMIT 1
                    )
                ORDER BY s.window_id
                """,
                (profile_key,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_snapshots(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) as n FROM usage_snapshots").fetchone()
        return int(row["n"])

    def apply_retention(self, retention_days: int, *, now: datetime | None = None) -> int:
        """Delete snapshots older than retention_days. Always logs before deleting.
        Returns number of rows deleted. Safe to call at most once/day by caller.
        """
        cutoff = (now or datetime.now(UTC))
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=retention_days)
        cutoff_iso = _iso(cutoff)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) as n FROM usage_snapshots WHERE observed_at_utc < ?", (cutoff_iso,)
            ).fetchone()
            to_delete = int(row["n"])
            if to_delete == 0:
                return 0
            connection.execute(
                "INSERT INTO refresh_log (event_utc, event_type, profile_key, detail) VALUES (?, ?, NULL, ?)",
                (
                    _iso(datetime.now(UTC)),
                    "retention_delete",
                    f"Deleting {to_delete} snapshot(s) older than {retention_days}d (cutoff {cutoff_iso})",
                ),
            )
            connection.execute("DELETE FROM usage_snapshots WHERE observed_at_utc < ?", (cutoff_iso,))
        return to_delete

    def delete_all_history(self, *, confirmed: bool) -> int:
        if not confirmed:
            raise ValueError("delete_all_history requires confirmed=True")
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) as n FROM usage_snapshots").fetchone()
            total = int(row["n"])
            connection.execute(
                "INSERT INTO refresh_log (event_utc, event_type, profile_key, detail) VALUES (?, ?, NULL, ?)",
                (
                    _iso(datetime.now(UTC)),
                    "manual_delete",
                    f"Manual full-history delete requested via API; deleting {total} snapshot(s)",
                ),
            )
            connection.execute("DELETE FROM usage_snapshots")
        return total

    # -------------------------------------------------------------- settings

    def get_setting(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # --------------------------------------------------------- notifications

    def was_notification_sent(self, dedupe_key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sent_notifications WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
        return row is not None

    def mark_notification_sent(
        self, dedupe_key: str, *, profile_key: str, window_id: str, event_type: str
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO sent_notifications "
                "(dedupe_key, profile_key, window_id, event_type, sent_utc) VALUES (?, ?, ?, ?, ?)",
                (dedupe_key, profile_key, window_id, event_type, _iso(datetime.now(UTC))),
            )
        return cursor.rowcount > 0

    def get_refresh_log(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM refresh_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
