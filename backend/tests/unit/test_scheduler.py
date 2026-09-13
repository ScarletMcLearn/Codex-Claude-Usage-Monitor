from __future__ import annotations

import pytest

from claude_codex_monitor.scheduler import RefreshScheduler


class _Discovery:
    def __init__(self) -> None:
        self.calls = 0

    def discover_all(self):
        self.calls += 1


class _Usage:
    def __init__(self) -> None:
        self.calls = 0

    def refresh_all(self):
        self.calls += 1
        return ["profile"]


class _Settings:
    refresh_interval_seconds = 30
    auto_refresh_enabled = True

    def get(self):
        return self


class _Forensics:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def refresh(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("jsonl scan failed")
        return {"sources_scanned": 2, "events_processed": 3}


@pytest.mark.asyncio
async def test_scheduler_refresh_runs_forensics_after_usage():
    discovery = _Discovery()
    usage = _Usage()
    forensics = _Forensics()
    scheduler = RefreshScheduler(discovery, usage, _Settings(), forensics)  # type: ignore[arg-type]

    await scheduler.refresh_all_locked()

    assert discovery.calls == 1
    assert usage.calls == 1
    assert forensics.calls == 1
    assert scheduler.last_refresh_ok is True


@pytest.mark.asyncio
async def test_scheduler_forensics_failure_does_not_fail_usage_refresh():
    discovery = _Discovery()
    usage = _Usage()
    forensics = _Forensics(fail=True)
    scheduler = RefreshScheduler(discovery, usage, _Settings(), forensics)  # type: ignore[arg-type]

    await scheduler.refresh_all_locked()

    assert usage.calls == 1
    assert forensics.calls == 1
    assert scheduler.last_refresh_ok is True
