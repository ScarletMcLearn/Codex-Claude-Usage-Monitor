from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Isolate all app data (DB, settings) into a per-test temp dir."""
    monkeypatch.setenv("CCM_DATA_DIR", str(tmp_path / "ccm_data"))
    return tmp_path / "ccm_data"


@pytest.fixture()
def store(tmp_data_dir):
    from claude_codex_monitor.db.store import Store

    return Store(path=tmp_data_dir / "history.sqlite3")
