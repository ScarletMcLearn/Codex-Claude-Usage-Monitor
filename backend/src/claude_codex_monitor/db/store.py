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


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


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
            _ensure_column(connection, "usage_snapshots", "used_units", "REAL")
            _ensure_column(connection, "usage_snapshots", "max_units", "REAL")
            for column, column_type in (
                ("source_identity", "TEXT"),
                ("head_fingerprint", "TEXT"),
                ("duplicate_events", "INTEGER NOT NULL DEFAULT 0"),
                ("checkpoint_reset_count", "INTEGER NOT NULL DEFAULT 0"),
                ("checkpoint_reset_reason", "TEXT"),
                ("last_event_time_utc", "TEXT"),
                ("rotation_detected", "INTEGER NOT NULL DEFAULT 0"),
                ("truncation_detected", "INTEGER NOT NULL DEFAULT 0"),
                ("replacement_detected", "INTEGER NOT NULL DEFAULT 0"),
            ):
                _ensure_column(connection, "forensic_sources", column, column_type)
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                (str(SCHEMA_VERSION),),
            )
            for provider, name in (
                ("claude", "Claude Code"),
                ("codex", "Codex"),
                ("antigravity", "Antigravity"),
                ("free_ai", "Free-AI"),
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
        used_units: float | None = None,
        max_units: float | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO usage_snapshots
                    (profile_key, window_id, window_label, used_percent, used_units,
                     max_units, remaining_percent,
                     resets_at_utc, reset_confirmed, quality, unavailable_reason,
                     observed_at_utc, source_detail_json, is_reset_boundary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_key,
                    window_id,
                    window_label,
                    used_percent,
                    used_units,
                    max_units,
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
                    AND s.id = (
                        SELECT s2.id
                        FROM usage_snapshots s2
                        WHERE s2.profile_key = s.profile_key
                            AND s2.window_id = s.window_id
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

    # -------------------------------------------------------- forensic data

    def upsert_forensic_source(self, row: dict[str, Any]) -> None:
        now = _iso(datetime.now(UTC))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO forensic_sources
                    (source_id, agent, source_type, source_path, parser_version,
                     first_seen_utc, last_seen_utc, file_size, file_mtime_utc,
                     source_identity, head_fingerprint, checkpoint_offset,
                     events_processed, events_skipped, malformed_events, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_seen_utc = excluded.last_seen_utc,
                    file_size = excluded.file_size,
                    file_mtime_utc = excluded.file_mtime_utc,
                    source_identity = excluded.source_identity,
                    head_fingerprint = excluded.head_fingerprint,
                    last_error = excluded.last_error
                """,
                (
                    row["source_id"],
                    row["agent"],
                    row["source_type"],
                    row["source_path"],
                    row["parser_version"],
                    row.get("first_seen_utc") or now,
                    row.get("last_seen_utc") or now,
                    row.get("file_size"),
                    row.get("file_mtime_utc"),
                    row.get("source_identity"),
                    row.get("head_fingerprint"),
                    row.get("checkpoint_offset", 0),
                    row.get("events_processed", 0),
                    row.get("events_skipped", 0),
                    row.get("malformed_events", 0),
                    row.get("last_error"),
                ),
            )

    def update_forensic_source_checkpoint(
        self,
        source_id: str,
        *,
        checkpoint_offset: int,
        events_processed: int,
        events_skipped: int,
        malformed_events: int,
        duplicate_events: int = 0,
        reset_reason: str | None = None,
        last_event_time_utc: str | None = None,
        rotation_detected: bool = False,
        truncation_detected: bool = False,
        replacement_detected: bool = False,
        last_error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE forensic_sources
                SET checkpoint_offset = ?, events_processed = events_processed + ?,
                    events_skipped = events_skipped + ?, malformed_events = malformed_events + ?,
                    duplicate_events = duplicate_events + ?,
                    checkpoint_reset_count = checkpoint_reset_count + ?,
                    checkpoint_reset_reason = ?,
                    last_event_time_utc = COALESCE(?, last_event_time_utc),
                    rotation_detected = CASE WHEN ? THEN 1 ELSE rotation_detected END,
                    truncation_detected = CASE WHEN ? THEN 1 ELSE truncation_detected END,
                    replacement_detected = CASE WHEN ? THEN 1 ELSE replacement_detected END,
                    last_ingested_utc = ?, last_error = ?
                WHERE source_id = ?
                """,
                (
                    checkpoint_offset,
                    events_processed,
                    events_skipped,
                    malformed_events,
                    duplicate_events,
                    1 if reset_reason else 0,
                    reset_reason,
                    last_event_time_utc,
                    1 if rotation_detected else 0,
                    1 if truncation_detected else 0,
                    1 if replacement_detected else 0,
                    _iso(datetime.now(UTC)),
                    last_error,
                    source_id,
                ),
            )

    def get_forensic_source(self, source_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM forensic_sources WHERE source_id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def forensic_source_diagnostics(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_id, agent AS source, source_type, source_identity,
                       file_size, checkpoint_offset AS stored_checkpoint,
                       checkpoint_offset AS current_offset, last_event_time_utc,
                       parser_version, events_processed, malformed_events,
                       duplicate_events, checkpoint_reset_count,
                       checkpoint_reset_reason AS reset_reason,
                       rotation_detected, truncation_detected, replacement_detected,
                       last_error
                FROM forensic_sources
                ORDER BY last_seen_utc DESC, source_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_forensic_rows(
        self,
        *,
        sessions: list[dict[str, Any]],
        turns: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        commands: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
        raw_events: list[dict[str, Any]],
        file_accesses: list[dict[str, Any]] | None = None,
        relationships: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                for row in sessions:
                    connection.execute(
                        """
                        INSERT INTO forensic_sessions
                            (session_id, agent, provider, profile_id, model, model_variant,
                             project_path, repository_path, branch, worktree, started_at_utc,
                             ended_at_utc, source_id, raw_event_count, input_tokens,
                             output_tokens, total_tokens, cached_tokens, reasoning_tokens,
                             token_quality)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            ended_at_utc = COALESCE(excluded.ended_at_utc, ended_at_utc),
                            model = COALESCE(excluded.model, model),
                            project_path = COALESCE(excluded.project_path, project_path),
                            repository_path = COALESCE(excluded.repository_path, repository_path),
                            branch = COALESCE(excluded.branch, branch),
                            raw_event_count = raw_event_count + excluded.raw_event_count,
                            input_tokens = COALESCE(excluded.input_tokens, input_tokens),
                            output_tokens = COALESCE(excluded.output_tokens, output_tokens),
                            total_tokens = COALESCE(excluded.total_tokens, total_tokens),
                            cached_tokens = COALESCE(excluded.cached_tokens, cached_tokens),
                            reasoning_tokens = COALESCE(excluded.reasoning_tokens, reasoning_tokens),
                            token_quality = excluded.token_quality
                        """,
                        _session_tuple(row),
                    )
                for table, rows, columns in (
                    ("forensic_raw_events", raw_events, _RAW_EVENT_COLUMNS),
                    ("forensic_turns", turns, _TURN_COLUMNS),
                    ("forensic_messages", messages, _MESSAGE_COLUMNS),
                    ("forensic_tool_calls", tools, _TOOL_COLUMNS),
                    ("forensic_commands", commands, _COMMAND_COLUMNS),
                    ("forensic_context_blocks", contexts, _CONTEXT_COLUMNS),
                    ("forensic_file_accesses", file_accesses or [], _FILE_ACCESS_COLUMNS),
                    ("forensic_relationships", relationships or [], _RELATIONSHIP_COLUMNS),
                ):
                    if not rows:
                        continue
                    placeholders = ", ".join("?" for _ in columns)
                    names = ", ".join(columns)
                    sql = f"INSERT OR IGNORE INTO {table} ({names}) VALUES ({placeholders})"
                    connection.executemany(
                        sql, [tuple(_sqlite_value(row.get(c)) for c in columns) for row in rows]
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def forensic_overview(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = {}
            for name in (
                "forensic_sources",
                "forensic_sessions",
                "forensic_turns",
                "forensic_messages",
                "forensic_tool_calls",
                "forensic_commands",
                "forensic_context_blocks",
                "forensic_file_accesses",
                "forensic_relationships",
                "forensic_raw_events",
            ):
                counts[name] = int(connection.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"])
            agents = connection.execute(
                """
                SELECT agent, COUNT(*) AS sessions, SUM(COALESCE(total_tokens, 0)) AS total_tokens
                FROM forensic_sessions GROUP BY agent ORDER BY sessions DESC
                """
            ).fetchall()
            expensive = connection.execute(
                """
                SELECT turn_id, session_id, event_type, timestamp_utc, model,
                       input_tokens, output_tokens, total_tokens, token_quality,
                       user_preview, assistant_preview
                FROM forensic_turns
                ORDER BY COALESCE(total_tokens, 0) DESC, timestamp_utc DESC
                LIMIT 20
                """
            ).fetchall()
            duplicates = connection.execute(
                """
                SELECT content_hash, COUNT(*) AS occurrences, MAX(char_count) AS chars,
                       MAX(estimated_tokens) AS estimated_tokens,
                       MIN(first_seen_utc) AS first_seen_utc, MAX(first_seen_utc) AS latest_seen_utc,
                       MIN(category) AS category, MIN(source) AS source,
                       SUBSTR(MIN(text), 1, 240) AS preview
                FROM forensic_context_blocks
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                ORDER BY occurrences DESC, chars DESC
                LIMIT 20
                """
            ).fetchall()
        return {
            "counts": counts,
            "agents": [dict(row) for row in agents],
            "expensive_turns": [dict(row) for row in expensive],
            "repeated_context": [dict(row) for row in duplicates],
            "zero_token_counters": {
                "monitor_model_generation_requests": 0,
                "monitor_completion_requests": 0,
                "monitor_agent_prompt_invocations": 0,
            },
        }

    def list_forensic_sessions(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        where, params = _forensic_session_filter_sql(filters or {})
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM forensic_sessions
                {where}
                ORDER BY COALESCE(started_at_utc, ended_at_utc) DESC, session_id ASC
                LIMIT ? OFFSET ?
                """,
                (*params, limit + 1, offset),
            ).fetchall()
        items = [dict(row) for row in rows[:limit]]
        return {"items": items, "limit": limit, "offset": offset, "has_more": len(rows) > limit}

    def forensic_session_detail(self, session_id: str, *, limit: int = 100) -> dict[str, Any] | None:
        with self._connect() as connection:
            session = connection.execute(
                "SELECT * FROM forensic_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            turns = connection.execute(
                "SELECT * FROM forensic_turns WHERE session_id = ? ORDER BY turn_index LIMIT ?",
                (session_id, limit),
            ).fetchall()
            tools = connection.execute(
                "SELECT * FROM forensic_tool_calls WHERE session_id = ? LIMIT ?",
                (session_id, limit),
            ).fetchall()
            commands = connection.execute(
                "SELECT * FROM forensic_commands WHERE session_id = ? LIMIT ?",
                (session_id, limit),
            ).fetchall()
            contexts = connection.execute(
                """
                SELECT block_id, category, source, char_count, byte_count, line_count,
                       content_hash, estimated_tokens, token_quality, first_seen_utc,
                       SUBSTR(text, 1, 500) AS preview
                FROM forensic_context_blocks WHERE session_id = ?
                ORDER BY char_count DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            files = connection.execute(
                """
                SELECT * FROM forensic_file_accesses
                WHERE session_id = ? ORDER BY timestamp_utc, file_access_id LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            relationships = connection.execute(
                """
                SELECT * FROM forensic_relationships
                WHERE child_session_id = ? OR parent_session_id = ?
                ORDER BY timestamp_utc, relationship_id LIMIT ?
                """,
                (session_id, session_id, limit),
            ).fetchall()
        session_dict = dict(session)
        return {
            "session": session_dict,
            "turns": [dict(row) for row in turns],
            "tools": [dict(row) for row in tools],
            "commands": [dict(row) for row in commands],
            "context_blocks": [dict(row) for row in contexts],
            "file_accesses": [dict(row) for row in files],
            "relationships": [dict(row) for row in relationships],
            "usage_rollup": self.forensic_usage_rollup(session_id),
        }

    def forensic_usage_rollup(self, session_id: str) -> dict[str, Any]:
        eligible = {"sidechain_parent_message", "child_session"}
        with self._connect() as connection:
            session_rows = {
                row["session_id"]: dict(row)
                for row in connection.execute("SELECT * FROM forensic_sessions").fetchall()
            }
            edge_rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT * FROM forensic_relationships
                    WHERE parent_session_id IS NOT NULL AND child_session_id IS NOT NULL
                    ORDER BY relationship_id
                    """
                ).fetchall()
            ]
        direct = _usage_values(session_rows.get(session_id, {}))
        graph: dict[str, list[dict[str, Any]]] = {}
        skipped_edges = []
        relationship_types: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()
        for edge in edge_rows:
            etype = str(edge.get("relationship_type") or "")
            parent = str(edge.get("parent_session_id") or "")
            child = str(edge.get("child_session_id") or "")
            key = (parent, child, etype)
            if key in seen_edges:
                skipped_edges.append({"reason": "duplicate_edge", **edge})
                continue
            seen_edges.add(key)
            if etype not in eligible:
                skipped_edges.append({"reason": "ineligible_relationship_type", **edge})
                continue
            if not parent or not child or parent == child:
                skipped_edges.append({"reason": "self_or_missing_endpoint", **edge})
                continue
            graph.setdefault(parent, []).append(edge)
            relationship_types.add(etype)

        descendants: set[str] = set()
        cycles = []
        stack: list[tuple[str, tuple[str, ...]]] = [(session_id, (session_id,))]
        while stack:
            current, path = stack.pop()
            for edge in graph.get(current, []):
                child = str(edge["child_session_id"])
                if child in path:
                    cycles.append({"path": [*path, child], "relationship_id": edge["relationship_id"]})
                    continue
                if child in descendants:
                    continue
                descendants.add(child)
                if child in session_rows:
                    stack.append((child, (*path, child)))
                else:
                    skipped_edges.append({"reason": "orphan_child", **edge})
        descendant = _zero_usage()
        for descendant_id in sorted(descendants):
            descendant = _add_usage(descendant, _usage_values(session_rows.get(descendant_id, {})))
        return {
            "direct_usage": direct,
            "descendant_usage": descendant,
            "inclusive_usage": _add_usage(direct, descendant),
            "descendant_session_ids": sorted(descendants),
            "relationship_types_used": sorted(relationship_types),
            "cycles": cycles,
            "skipped_edges": skipped_edges,
            "quality": "derived",
            "available": bool(graph.get(session_id) or descendants),
            "unavailable_reason": None
            if graph.get(session_id) or descendants
            else "Unavailable from source relationship semantics",
        }

    def forensic_turn_detail(self, turn_id: str, *, limit: int = 200) -> dict[str, Any] | None:
        with self._connect() as connection:
            turn = connection.execute(
                "SELECT * FROM forensic_turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            if turn is None:
                return None
            session = connection.execute(
                "SELECT * FROM forensic_sessions WHERE session_id = ?", (turn["session_id"],)
            ).fetchone()
            messages = connection.execute(
                """
                SELECT message_id, role, timestamp_utc, char_count, byte_count, line_count,
                       content_hash, estimated_tokens, token_quality, raw_event_id,
                       SUBSTR(text, 1, 4000) AS preview
                FROM forensic_messages WHERE turn_id = ? LIMIT ?
                """,
                (turn_id, limit),
            ).fetchall()
            tools = connection.execute(
                """
                SELECT tool_call_id, tool_name, arguments_json, status, error, duration_ms,
                       output_chars, output_bytes, output_lines, content_hash, raw_event_id,
                       SUBSTR(output_text, 1, 4000) AS output_preview
                FROM forensic_tool_calls WHERE turn_id = ? LIMIT ?
                """,
                (turn_id, limit),
            ).fetchall()
            commands = connection.execute(
                """
                SELECT command_id, command, cwd, exit_code, output_chars, output_bytes,
                       output_lines, content_hash, raw_event_id,
                       SUBSTR(stdout_text, 1, 4000) AS stdout_preview,
                       SUBSTR(stderr_text, 1, 4000) AS stderr_preview
                FROM forensic_commands WHERE turn_id = ? LIMIT ?
                """,
                (turn_id, limit),
            ).fetchall()
            contexts = connection.execute(
                """
                SELECT block_id, category, source, char_count, byte_count, line_count,
                       content_hash, estimated_tokens, token_quality, first_seen_utc,
                       raw_event_id, SUBSTR(text, 1, 4000) AS preview
                FROM forensic_context_blocks WHERE turn_id = ? LIMIT ?
                """,
                (turn_id, limit),
            ).fetchall()
            raw_events = connection.execute(
                """
                SELECT raw_event_id, source_id, session_id, event_index, byte_offset,
                       timestamp_utc, event_type, content_hash, raw_json
                FROM forensic_raw_events WHERE raw_event_id = ? LIMIT ?
                """,
                (turn["raw_event_id"], limit),
            ).fetchall()
            files = connection.execute(
                """
                SELECT * FROM forensic_file_accesses
                WHERE turn_id = ? ORDER BY timestamp_utc, file_access_id LIMIT ?
                """,
                (turn_id, limit),
            ).fetchall()
            relationships = connection.execute(
                """
                SELECT * FROM forensic_relationships
                WHERE child_turn_id = ? OR parent_turn_id = ?
                ORDER BY timestamp_utc, relationship_id LIMIT ?
                """,
                (turn_id, turn_id, limit),
            ).fetchall()
        return {
            "session": dict(session) if session else None,
            "turn": dict(turn),
            "messages": [dict(row) for row in messages],
            "tools": [dict(row) for row in tools],
            "commands": [dict(row) for row in commands],
            "context_blocks": [dict(row) for row in contexts],
            "file_accesses": [dict(row) for row in files],
            "relationships": [dict(row) for row in relationships],
            "raw_events": [dict(row) for row in raw_events],
        }

    def forensic_hotspots(self, *, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as connection:
            tools = connection.execute(
                """
                SELECT tool_name, COUNT(*) AS calls, SUM(COALESCE(output_bytes, 0)) AS output_bytes,
                       SUM(CASE WHEN status = 'error' OR error IS NOT NULL THEN 1 ELSE 0 END) AS failures
                FROM forensic_tool_calls
                GROUP BY tool_name
                ORDER BY calls DESC, output_bytes DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            commands = connection.execute(
                """
                SELECT command, COUNT(*) AS calls, SUM(COALESCE(output_bytes, 0)) AS output_bytes,
                       SUM(CASE WHEN exit_code IS NOT NULL AND exit_code != 0 THEN 1 ELSE 0 END) AS failures
                FROM forensic_commands
                GROUP BY command
                ORDER BY calls DESC, output_bytes DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            context = connection.execute(
                """
                SELECT category, source, content_hash, COUNT(*) AS occurrences,
                       MAX(byte_count) AS bytes, MAX(estimated_tokens) AS estimated_tokens,
                       SUBSTR(MIN(text), 1, 240) AS preview
                FROM forensic_context_blocks
                GROUP BY category, source, content_hash
                ORDER BY occurrences DESC, bytes DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            files = connection.execute(
                """
                SELECT normalized_path, MIN(path) AS path, operation,
                       COUNT(*) AS accesses,
                       SUM(COALESCE(repeated_path, 0)) AS rereads,
                       SUM(COALESCE(repeated_content, 0)) AS repeated_identical_content,
                       SUM(COALESCE(characters, 0)) AS characters,
                       SUM(COALESCE(estimated_tokens, 0)) AS estimated_tokens,
                       MAX(COALESCE(characters, 0)) AS largest_injection_chars,
                       COUNT(DISTINCT session_id) AS sessions,
                       COUNT(DISTINCT turn_id) AS turns
                FROM forensic_file_accesses
                GROUP BY normalized_path, operation
                ORDER BY accesses DESC, characters DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {
            "tools": [dict(row) for row in tools],
            "commands": [dict(row) for row in commands],
            "context": [dict(row) for row in context],
            "files": [dict(row) for row in files],
        }

    def list_forensic_table(self, table: str) -> list[dict[str, Any]]:
        allowed = {
            "agents": (
                "SELECT agent, provider, model, COUNT(*) AS sessions, "
                "SUM(COALESCE(total_tokens, 0)) AS total_tokens "
                "FROM forensic_sessions GROUP BY agent, provider, model"
            ),
            "sessions": "SELECT * FROM forensic_sessions",
            "turns": "SELECT * FROM forensic_turns",
            "messages": "SELECT * FROM forensic_messages",
            "tools": "SELECT * FROM forensic_tool_calls",
            "commands": "SELECT * FROM forensic_commands",
            "context-blocks": "SELECT * FROM forensic_context_blocks",
            "file-accesses": "SELECT * FROM forensic_file_accesses",
            "relationships": "SELECT * FROM forensic_relationships",
            "raw-events": "SELECT * FROM forensic_raw_events",
        }
        if table not in allowed:
            raise KeyError(table)
        with self._connect() as connection:
            rows = connection.execute(allowed[table]).fetchall()
        return [dict(row) for row in rows]


_RAW_EVENT_COLUMNS = (
    "raw_event_id", "source_id", "session_id", "event_index", "byte_offset",
    "timestamp_utc", "event_type", "content_hash", "raw_json",
)
_TURN_COLUMNS = (
    "turn_id", "session_id", "turn_index", "request_id", "response_id", "role",
    "event_type", "timestamp_utc", "model", "input_tokens", "output_tokens",
    "total_tokens", "cached_tokens", "cache_write_tokens", "reasoning_tokens",
    "context_tokens", "duration_ms", "token_quality", "provenance_json",
    "user_preview", "assistant_preview", "content_hash", "raw_event_id",
)
_MESSAGE_COLUMNS = (
    "message_id", "session_id", "turn_id", "role", "timestamp_utc", "text",
    "char_count", "byte_count", "line_count", "content_hash", "estimated_tokens",
    "token_quality", "source_id", "raw_event_id",
)
_TOOL_COLUMNS = (
    "tool_call_id", "session_id", "turn_id", "tool_name", "arguments_json",
    "output_text", "status", "error", "duration_ms", "output_chars",
    "output_bytes", "output_lines", "content_hash", "raw_event_id",
)
_COMMAND_COLUMNS = (
    "command_id", "session_id", "turn_id", "command", "cwd", "exit_code",
    "stdout_text", "stderr_text", "output_chars", "output_bytes",
    "output_lines", "content_hash", "raw_event_id",
)
_CONTEXT_COLUMNS = (
    "block_id", "session_id", "turn_id", "category", "source", "text",
    "char_count", "byte_count", "line_count", "content_hash", "estimated_tokens",
    "token_quality", "first_seen_utc", "raw_event_id",
)
_FILE_ACCESS_COLUMNS = (
    "file_access_id", "source_event_id", "session_id", "turn_id", "agent",
    "operation", "path", "normalized_path", "access_kind", "requested_range",
    "actual_range", "line_start", "line_end", "line_count", "bytes", "characters",
    "content_hash", "repeated_path", "repeated_content", "entered_model_context",
    "reported_tokens", "estimated_tokens", "token_quality", "timestamp_utc",
    "provenance_json",
)
_RELATIONSHIP_COLUMNS = (
    "relationship_id", "source", "parent_session_id", "parent_turn_id",
    "parent_agent", "child_session_id", "child_turn_id", "child_agent",
    "relationship_type", "evidence_json", "timestamp_utc", "confidence",
)


def _forensic_session_filter_sql(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses = ["WHERE 1=1"]
    params: list[Any] = []
    mapping = {
        "agent": "agent",
        "provider": "provider",
        "model": "model",
        "project": "project_path",
        "repository": "repository_path",
        "branch": "branch",
        "worktree": "worktree",
        "session_id": "session_id",
        "token_quality": "token_quality",
    }
    for key, column in mapping.items():
        value = filters.get(key)
        if value:
            if key in {"project", "repository", "worktree"}:
                clauses.append(f"AND {column} LIKE ?")
                params.append(f"%{value}%")
            else:
                clauses.append(f"AND {column} = ?")
                params.append(value)
    if filters.get("since_utc"):
        clauses.append("AND COALESCE(started_at_utc, ended_at_utc) >= ?")
        params.append(filters["since_utc"])
    if filters.get("until_utc"):
        clauses.append("AND COALESCE(started_at_utc, ended_at_utc) <= ?")
        params.append(filters["until_utc"])
    for key, column in (
        ("min_total_tokens", "total_tokens"),
        ("min_input_tokens", "input_tokens"),
        ("min_output_tokens", "output_tokens"),
    ):
        value = filters.get(key)
        if value is not None:
            clauses.append(f"AND COALESCE({column}, 0) >= ?")
            params.append(value)
    if filters.get("has_tools"):
        clauses.append(
            "AND EXISTS (SELECT 1 FROM forensic_tool_calls t "
            "WHERE t.session_id = forensic_sessions.session_id)"
        )
    if filters.get("has_commands"):
        clauses.append(
            "AND EXISTS (SELECT 1 FROM forensic_commands c "
            "WHERE c.session_id = forensic_sessions.session_id)"
        )
    if filters.get("has_child_relationships"):
        clauses.append(
            "AND EXISTS (SELECT 1 FROM forensic_relationships r "
            "WHERE r.parent_session_id = forensic_sessions.session_id "
            "OR r.child_session_id = forensic_sessions.session_id)"
        )
    return " ".join(clauses), params


def _zero_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    }


def _usage_values(row: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(row.get(key) or 0)
        for key in _zero_usage()
    }


def _add_usage(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: int(left.get(key) or 0) + int(right.get(key) or 0) for key in _zero_usage()}


def _session_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["session_id"], row["agent"], row.get("provider"), row.get("profile_id"),
        row.get("model"), row.get("model_variant"), row.get("project_path"),
        row.get("repository_path"), row.get("branch"), row.get("worktree"),
        row.get("started_at_utc"), row.get("ended_at_utc"), row["source_id"],
        row.get("raw_event_count", 0), row.get("input_tokens"), row.get("output_tokens"),
        row.get("total_tokens"), row.get("cached_tokens"), row.get("reasoning_tokens"),
        row.get("token_quality", "unknown"),
    )


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value
