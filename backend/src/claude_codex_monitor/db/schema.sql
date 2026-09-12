-- Claude Codex Monitor own SQLite schema.
-- WAL journaling; never silently delete (retention sweep always logs to
-- refresh_log before deleting; manual full-history delete requires explicit
-- confirm at the API layer).

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    provider TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    profile_key       TEXT PRIMARY KEY,   -- "provider:profile_id"
    provider          TEXT NOT NULL,
    profile_id        TEXT NOT NULL,
    label             TEXT NOT NULL,
    friendly_name     TEXT,
    sanitized_source  TEXT NOT NULL,
    discovery_source  TEXT NOT NULL,
    is_active         INTEGER NOT NULL DEFAULT 1,
    first_seen_utc    TEXT NOT NULL,
    last_seen_utc     TEXT NOT NULL,
    last_refresh_utc  TEXT,
    last_success_utc  TEXT,
    last_error        TEXT
);

CREATE TABLE IF NOT EXISTS usage_snapshots (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key        TEXT NOT NULL,
    window_id          TEXT NOT NULL,
    window_label       TEXT,
    used_percent       REAL,
    used_units         REAL,
    max_units          REAL,
    remaining_percent  REAL,
    resets_at_utc      TEXT,
    reset_confirmed    INTEGER NOT NULL DEFAULT 0,
    quality            TEXT NOT NULL,
    unavailable_reason TEXT,
    observed_at_utc    TEXT NOT NULL,
    source_detail_json TEXT,
    is_reset_boundary  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_snapshots_profile_window_time
    ON usage_snapshots (profile_key, window_id, observed_at_utc);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refresh_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_utc  TEXT NOT NULL,
    event_type TEXT NOT NULL,   -- "refresh_success" | "refresh_failure" | "retention_delete" | "manual_delete" | "backoff"
    profile_key TEXT,
    detail     TEXT
);

CREATE TABLE IF NOT EXISTS sent_notifications (
    dedupe_key  TEXT PRIMARY KEY,
    profile_key TEXT NOT NULL,
    window_id   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    sent_utc    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sent_notifications_profile
    ON sent_notifications (profile_key, window_id);

-- Passive forensic telemetry. All rows originate from local files/logs or
-- deterministic derived values. Unknown token values stay NULL, never 0.

CREATE TABLE IF NOT EXISTS forensic_sources (
    source_id          TEXT PRIMARY KEY,
    agent             TEXT NOT NULL,
    source_type        TEXT NOT NULL,
    source_path        TEXT NOT NULL,
    parser_version     TEXT NOT NULL,
    first_seen_utc     TEXT NOT NULL,
    last_seen_utc      TEXT NOT NULL,
    last_ingested_utc  TEXT,
    file_size          INTEGER,
    file_mtime_utc     TEXT,
    checkpoint_offset  INTEGER NOT NULL DEFAULT 0,
    events_processed   INTEGER NOT NULL DEFAULT 0,
    events_skipped     INTEGER NOT NULL DEFAULT 0,
    malformed_events   INTEGER NOT NULL DEFAULT 0,
    last_error         TEXT
);

CREATE TABLE IF NOT EXISTS forensic_sessions (
    session_id         TEXT PRIMARY KEY,
    agent              TEXT NOT NULL,
    provider           TEXT,
    profile_id         TEXT,
    model              TEXT,
    model_variant      TEXT,
    project_path       TEXT,
    repository_path    TEXT,
    branch             TEXT,
    worktree           TEXT,
    started_at_utc     TEXT,
    ended_at_utc       TEXT,
    source_id          TEXT NOT NULL,
    raw_event_count    INTEGER NOT NULL DEFAULT 0,
    input_tokens       INTEGER,
    output_tokens      INTEGER,
    total_tokens       INTEGER,
    cached_tokens      INTEGER,
    reasoning_tokens   INTEGER,
    token_quality      TEXT NOT NULL DEFAULT 'unknown',
    FOREIGN KEY(source_id) REFERENCES forensic_sources(source_id)
);

CREATE TABLE IF NOT EXISTS forensic_turns (
    turn_id            TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    turn_index         INTEGER NOT NULL,
    request_id         TEXT,
    response_id        TEXT,
    role               TEXT,
    event_type         TEXT,
    timestamp_utc      TEXT,
    model              TEXT,
    input_tokens       INTEGER,
    output_tokens      INTEGER,
    total_tokens       INTEGER,
    cached_tokens      INTEGER,
    cache_write_tokens INTEGER,
    reasoning_tokens   INTEGER,
    context_tokens     INTEGER,
    duration_ms        INTEGER,
    token_quality      TEXT NOT NULL DEFAULT 'unknown',
    provenance_json    TEXT,
    user_preview       TEXT,
    assistant_preview  TEXT,
    content_hash       TEXT,
    raw_event_id       TEXT,
    FOREIGN KEY(session_id) REFERENCES forensic_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS forensic_messages (
    message_id         TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    turn_id            TEXT,
    role               TEXT NOT NULL,
    timestamp_utc      TEXT,
    text               TEXT,
    char_count         INTEGER NOT NULL,
    byte_count         INTEGER NOT NULL,
    line_count         INTEGER NOT NULL,
    content_hash       TEXT NOT NULL,
    estimated_tokens   INTEGER,
    token_quality      TEXT NOT NULL DEFAULT 'estimated',
    source_id          TEXT NOT NULL,
    raw_event_id       TEXT,
    FOREIGN KEY(session_id) REFERENCES forensic_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS forensic_tool_calls (
    tool_call_id       TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    turn_id            TEXT,
    tool_name          TEXT NOT NULL,
    arguments_json     TEXT,
    output_text        TEXT,
    status             TEXT,
    error              TEXT,
    duration_ms        INTEGER,
    output_chars       INTEGER,
    output_bytes       INTEGER,
    output_lines       INTEGER,
    content_hash       TEXT,
    raw_event_id       TEXT,
    FOREIGN KEY(session_id) REFERENCES forensic_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS forensic_commands (
    command_id         TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    turn_id            TEXT,
    command            TEXT NOT NULL,
    cwd                TEXT,
    exit_code          INTEGER,
    stdout_text        TEXT,
    stderr_text        TEXT,
    output_chars       INTEGER,
    output_bytes       INTEGER,
    output_lines       INTEGER,
    content_hash       TEXT,
    raw_event_id       TEXT,
    FOREIGN KEY(session_id) REFERENCES forensic_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS forensic_context_blocks (
    block_id           TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    turn_id            TEXT,
    category           TEXT NOT NULL,
    source             TEXT NOT NULL,
    text               TEXT,
    char_count         INTEGER NOT NULL,
    byte_count         INTEGER NOT NULL,
    line_count         INTEGER NOT NULL,
    content_hash       TEXT NOT NULL,
    estimated_tokens   INTEGER,
    token_quality      TEXT NOT NULL DEFAULT 'estimated',
    first_seen_utc     TEXT,
    raw_event_id       TEXT,
    FOREIGN KEY(session_id) REFERENCES forensic_sessions(session_id)
);

CREATE TABLE IF NOT EXISTS forensic_raw_events (
    raw_event_id       TEXT PRIMARY KEY,
    source_id          TEXT NOT NULL,
    session_id         TEXT,
    event_index        INTEGER NOT NULL,
    byte_offset        INTEGER NOT NULL,
    timestamp_utc      TEXT,
    event_type         TEXT,
    content_hash       TEXT NOT NULL,
    raw_json           TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES forensic_sources(source_id)
);

CREATE TABLE IF NOT EXISTS forensic_exports (
    export_id          TEXT PRIMARY KEY,
    created_at_utc     TEXT NOT NULL,
    export_type        TEXT NOT NULL,
    filters_json       TEXT NOT NULL,
    file_path          TEXT NOT NULL,
    warning_ack        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_forensic_sessions_agent
    ON forensic_sessions (agent, started_at_utc);
CREATE INDEX IF NOT EXISTS idx_forensic_turns_session
    ON forensic_turns (session_id, turn_index);
CREATE INDEX IF NOT EXISTS idx_forensic_messages_hash
    ON forensic_messages (content_hash);
CREATE INDEX IF NOT EXISTS idx_forensic_context_hash
    ON forensic_context_blocks (content_hash);
CREATE INDEX IF NOT EXISTS idx_forensic_tools_session
    ON forensic_tool_calls (session_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_forensic_commands_session
    ON forensic_commands (session_id, command);
