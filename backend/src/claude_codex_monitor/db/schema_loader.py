"""Load schema.sql as text, independent of current working directory."""

from __future__ import annotations

from pathlib import Path

SCHEMA_SQL = (Path(__file__).resolve().parent / "schema.sql").read_text(encoding="utf-8")
