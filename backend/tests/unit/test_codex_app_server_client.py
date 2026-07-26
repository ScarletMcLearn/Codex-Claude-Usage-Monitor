from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.vendor.codex_appserver.app_server_client import (
    build_isolated_env,
    parse_rate_limits,
    parse_ts,
    safe_account_label,
)
from claude_codex_monitor.vendor.codex_appserver.models import CodexProfileCandidate
from tests.fixtures.codex_rate_limit_payloads import (
    ACCOUNT_AUTHENTICATED,
    ACCOUNT_UNAUTHENTICATED,
    RATE_LIMITS_BY_LIMIT_ID,
    RATE_LIMITS_EMPTY,
    RATE_LIMITS_PRIMARY_ONLY,
)


def test_isolated_env_only_has_expected_keys(monkeypatch):
    monkeypatch.setenv("SOME_SECRET", "should-not-appear")
    env = build_isolated_env(Path("C:/fake/.codex"))
    assert "SOME_SECRET" not in env
    assert env["CODEX_HOME"] == str(Path("C:/fake/.codex"))


def test_safe_account_label_authenticated():
    status, label, identity = safe_account_label(ACCOUNT_AUTHENTICATED)
    assert status == "authenticated"
    assert "plus" in label


def test_safe_account_label_unauthenticated():
    status, _, _ = safe_account_label(ACCOUNT_UNAUTHENTICATED)
    assert status == "unauthenticated"


def test_safe_account_label_none_is_unknown():
    status, label, identity = safe_account_label(None)
    assert status == "unknown"


def test_parse_ts_iso_z():
    dt = parse_ts("2026-08-01T00:00:00Z")
    assert dt is not None
    assert dt.year == 2026


def test_parse_ts_invalid_is_none():
    assert parse_ts("not-a-date") is None
    assert parse_ts(None) is None


def _profile(home: Path) -> CodexProfileCandidate:
    return CodexProfileCandidate(label="default", kind="default home", codex_home=home)


def test_parse_rate_limits_primary_only(tmp_path):
    windows = parse_rate_limits(
        _profile(tmp_path), "test@example.invalid", "id", RATE_LIMITS_PRIMARY_ONLY
    )
    assert len(windows) == 1
    assert windows[0].window_name == "primary"
    assert windows[0].used_percent == 37


def test_parse_rate_limits_secondary_present_when_given(tmp_path):
    windows = parse_rate_limits(
        _profile(tmp_path), "test@example.invalid", "id", RATE_LIMITS_BY_LIMIT_ID
    )
    names = {w.window_name for w in windows}
    assert names == {"primary", "secondary"}


def test_parse_rate_limits_empty_payload_yields_no_windows(tmp_path):
    windows = parse_rate_limits(_profile(tmp_path), "test@example.invalid", "id", RATE_LIMITS_EMPTY)
    assert windows == []
