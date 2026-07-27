from __future__ import annotations

import time
from pathlib import Path

import pytest

from claude_codex_monitor.adapters.claude_adapter import ClaudeProviderAdapter
from claude_codex_monitor.models.profile import ProfileStatus
from claude_codex_monitor.models.usage import DataQuality
from claude_codex_monitor.vendor.claude_statusline.state_reader import (
    ClaudeNotifierStateReader,
    WindowReading,
)
from claude_codex_monitor.vendor.claude_usage_command import (
    ClaudeUsageCommandResult,
    ClaudeUsageCommandWindow,
)


@pytest.fixture(autouse=True)
def _disable_usage_command(monkeypatch):
    monkeypatch.setenv("CCM_CLAUDE_USAGE_COMMAND", "0")


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
    old_time = time.time() - 11 * 60  # 11 minutes ago > 10m threshold
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, old_time, None, None, False)]
    )
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.STALE
    assert limits[0].used_percent == 42.0  # value preserved, just re-labeled
    assert "statusline has not reported newer data" in limits[0].unavailable_reason


def test_reading_inside_freshness_window_is_verified():
    adapter = ClaudeProviderAdapter()
    recent_time = time.time() - 9 * 60
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, recent_time, None, None, False)]
    )
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.VERIFIED


def test_never_fabricates_when_no_windows_captured_yet():
    adapter = ClaudeProviderAdapter()
    adapter._reader = lambda: _FakeReader([])
    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)
    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert limits[0].used_percent is None


def test_usage_command_windows_override_statusline(monkeypatch):
    monkeypatch.setenv("CCM_CLAUDE_USAGE_COMMAND", "1")
    now = time.time()
    adapter = ClaudeProviderAdapter()
    adapter._run_usage_command = lambda profile: ClaudeUsageCommandResult(
        ok=True,
        reason=None,
        output="5-hour 100%",
        windows=[ClaudeUsageCommandWindow("five_hour", 100.0, now)],
        ran_at_utc=now,
    )
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, now, None, None, False)]
    )

    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)

    assert raw["source"] == "claude_usage_command"
    assert limits[0].quality == DataQuality.VERIFIED
    assert limits[0].used_percent == 100.0
    assert limits[0].source_detail["source"] == "claude_usage_command"


def test_usage_command_without_percent_falls_back_to_statusline(monkeypatch):
    monkeypatch.setenv("CCM_CLAUDE_USAGE_COMMAND", "1")
    now = time.time()
    adapter = ClaudeProviderAdapter()
    adapter._run_usage_command = lambda profile: ClaudeUsageCommandResult(
        ok=True,
        reason="no parse",
        output="Last 24h",
        windows=[],
        ran_at_utc=now,
    )
    adapter._reader = lambda: _FakeReader(
        [WindowReading("pid", "five_hour", 42.0, 1_900_000_000, now, None, None, False)]
    )

    raw = adapter.fetch_usage(_profile())
    limits = adapter.parse_usage(_profile(), raw)

    assert raw["source"] == "claude_usage_notifier_db"
    assert limits[0].used_percent == 42.0
    assert limits[0].source_detail["usage_command_reason"] == "no parse"
