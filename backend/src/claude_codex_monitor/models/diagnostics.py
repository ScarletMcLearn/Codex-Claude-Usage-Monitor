"""Diagnostics model - sanitized, no secrets/full file contents ever."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProfileDiagnostics(BaseModel):
    provider: str
    profile_id: str
    profile_key: str
    discovery_source: str
    sanitized_config_path: str
    last_command_result: str | None = None  # short sanitized summary, never raw stdout
    parser_used: str | None = None
    last_successful_query_utc: datetime | None = None
    current_error: str | None = None
    suggested_action: str | None = None
    executable_path_sanitized: str | None = None
    notifier_db_available: bool | None = None  # Claude only
    notifier_db_reason: str | None = None
