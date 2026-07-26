from __future__ import annotations

import time
from pathlib import Path

from claude_codex_monitor.adapters.claude_adapter import ClaudeProviderAdapter
from claude_codex_monitor.models.profile import ProfileStatus
from claude_codex_monitor.models.usage import DataQuality
from claude_codex_monitor.vendor.claude_statusline.state_reader import (
    ClaudeNotifierStateReader,
    WindowReading,
)


class _FakeReader(ClaudeNotifierStateReader):
    def __init__(self, windows):
        super().__init__(Path("unused"))
        self._windows = windows

    def is_available(self):
        return True

    def get_windows_for_profile(self, profile_id):
        return self._windows


def _profile() -> ProfileStatus:
    return ProfileStatus(
        provider="claude",
        profile_id="pid",
        profile_key="claude:pid",
        label="default",
        sanitized_source="~/.claude",
        discovery_source="default",
    )


def test_no_db_reports_unavailable_with_reason(tmp_path):
    adapter = ClaudeProviderAdapter(notifier_db_path=tmp_path / "does_not_exist.sqlite3")
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert len(limits) == 1
    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert "not found" in limits[0].unavailable_reason.lower()


def test_fresh_reading_is_verified():
    adapter = ClaudeProviderAdapter()
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, time.time(), None, None, False)]
    )
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.VERIFIED
    assert limits[0].used_percent == 42.0
    assert limits[0].remaining_percent == 58.0


def test_old_reading_is_stale_not_fabricated():
    adapter = ClaudeProviderAdapter()
    old_time = time.time() - 7 * 3600  # 7 hours ago > 6h threshold
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, old_time, None, None, False)]
    )
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.STALE
    assert limits[0].used_percent == 42.0  # value preserved, just re-labeled


def test_never_fabricates_when_no_windows_captured_yet():
    adapter = ClaudeProviderAdapter()
    adapter._reader = lambda: _FakeReader([])
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert limits[0].used_percent is None
