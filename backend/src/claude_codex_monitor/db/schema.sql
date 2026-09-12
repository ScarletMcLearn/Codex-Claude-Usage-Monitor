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
