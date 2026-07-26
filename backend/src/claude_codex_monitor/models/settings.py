"""User-editable settings, persisted as KV JSON in the app's own SQLite."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileOverride(BaseModel):
    provider: str
    profile_id: str
    enabled: bool = True
    friendly_name: str | None = None


class Settings(BaseModel):
    auto_refresh_enabled: bool = True
    refresh_interval_seconds: int = 300
    history_retention_days: int = 90
    theme: str = "system"  # "light" | "dark" | "system"
    display_timezone: str = "Asia/Dhaka"
    hide_sensitive_paths: bool = True
    notifications_enabled: bool = True
    notify_at_80_percent: bool = True
    notify_at_95_percent: bool = True
    notify_on_exhaustion: bool = True
    notify_on_auth_required: bool = True
    notify_on_repeated_failures: bool = True
    notify_on_reset: bool = True
    profile_overrides: list[ProfileOverride] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class SettingsPatch(BaseModel):
    """All fields optional - PATCH semantics."""

    auto_refresh_enabled: bool | None = None
    refresh_interval_seconds: int | None = None
    history_retention_days: int | None = None
    theme: str | None = None
    display_timezone: str | None = None
    hide_sensitive_paths: bool | None = None
    notifications_enabled: bool | None = None
    notify_at_80_percent: bool | None = None
    notify_at_95_percent: bool | None = None
    notify_on_exhaustion: bool | None = None
    notify_on_auth_required: bool | None = None
    notify_on_repeated_failures: bool | None = None
    notify_on_reset: bool | None = None
    profile_overrides: list[ProfileOverride] | None = None
