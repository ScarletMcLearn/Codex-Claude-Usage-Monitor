"""Data models for Google Antigravity profile discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AntigravityProfileCandidate:
    label: str
    kind: str
    config_home: Path
    source: str = ""
    executable: Path | None = None
    project_id: str | None = None
    profile_arg: str | None = None
