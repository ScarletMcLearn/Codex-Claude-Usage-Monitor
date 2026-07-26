# Adapted from I:\Projects\Automation\Codex\Notifications\src\ai_usage_notifier
# (not imported at runtime; copied and modified for this project).
"""Data models for Codex CLI profile discovery and app-server probing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexProfileCandidate:
    label: str
    kind: str  # "default home" | "isolated home" | "named config profile"
    codex_home: Path
    codex_executable: Path | None = None
    profile_arg: str | None = None
    source: str = ""


@dataclass(frozen=True)
class LimitWindow:
    source_id: str
    profile_labels: tuple[str, ...]
    account_label: str
    limit_id: str
    window_name: str  # "primary" | "secondary" - only "primary" is reliably present
    window_duration_mins: int | None
    used_percent: int | None
    resets_at: datetime | None
    plan_type: str | None = None
    raw_limit_name: str | None = None

    @property
    def event_source(self) -> str:
        base = f"{self.source_id}|{self.account_label}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


@dataclass
class ProbeResult:
    profile: CodexProfileCandidate
    ok: bool
    account_label: str = "unknown"
    account_identity: str = "unknown"
    rate_limits: list[LimitWindow] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    error: str | None = None
