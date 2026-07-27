from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.adapters.codex_adapter import CodexProviderAdapter
from claude_codex_monitor.models.profile import ProfileStatus
from claude_codex_monitor.models.usage import DataQuality
from claude_codex_monitor.vendor.codex_appserver.models import (
    CodexProfileCandidate,
    LimitWindow,
    ProbeResult,
)


def _profile() -> ProfileStatus:
    return ProfileStatus(
        provider="codex",
        profile_id="c:\\fake\\.codex",
        profile_key="codex:c:\\fake\\.codex",
        label="default",
        sanitized_source="~/.codex",
        discovery_source="default home",
    )


def test_probe_failure_yields_unavailable_with_reason():
    adapter = CodexProviderAdapter()
    result = ProbeResult(profile=None, ok=False, error="Authentication required")
    limits = adapter.parse_usage(_profile(), result)
    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert "authentication" in limits[0].unavailable_reason.lower()


def test_secondary_window_missing_is_unavailable_not_zero():
    candidate = CodexProfileCandidate(label="default", kind="default home", codex_home=Path("C:/fake/.codex"))
    windows = [
        LimitWindow(
            source_id="s",
            profile_labels=("default",),
            account_label="a",
            limit_id="codex-usage",
            window_name="primary",
            window_duration_mins=10080,
            used_percent=50,
            resets_at=None,
        )
    ]
    result = ProbeResult(profile=candidate, ok=True, account_label="a", rate_limits=windows)
    adapter = CodexProviderAdapter()
    limits = adapter.parse_usage(_profile(), result)
    names = {item.window_id for item in limits}
    assert names == {"primary"}  # secondary never fabricated as a 0% row
    assert limits[0].window_label == "7-day"
    assert limits[0].used_percent == 50
    assert limits[0].quality == DataQuality.VERIFIED


def test_codex_duration_labels_match_human_windows():
    candidate = CodexProfileCandidate(label="default", kind="default home", codex_home=Path("C:/fake/.codex"))
    windows = [
        LimitWindow(
            source_id="s",
            profile_labels=("default",),
            account_label="a",
            limit_id="codex-usage",
            window_name="primary",
            window_duration_mins=10080,
            used_percent=50,
            resets_at=None,
        ),
        LimitWindow(
            source_id="s",
            profile_labels=("default",),
            account_label="a",
            limit_id="codex-usage",
            window_name="secondary",
            window_duration_mins=300,
            used_percent=10,
            resets_at=None,
        ),
    ]
    result = ProbeResult(profile=candidate, ok=True, account_label="a", rate_limits=windows)
    adapter = CodexProviderAdapter()
    limits = adapter.parse_usage(_profile(), result)

    assert [(item.window_id, item.window_label) for item in limits] == [
        ("primary", "7-day"),
        ("secondary", "5-hour"),
    ]


def test_used_percent_none_is_unavailable_not_zero():
    candidate = CodexProfileCandidate(label="default", kind="default home", codex_home=Path("C:/fake/.codex"))
    windows = [
        LimitWindow(
            source_id="s",
            profile_labels=("default",),
            account_label="a",
            limit_id="codex-usage",
            window_name="primary",
            window_duration_mins=10080,
            used_percent=None,
            resets_at=None,
        )
    ]
    result = ProbeResult(profile=candidate, ok=True, account_label="a", rate_limits=windows)
    adapter = CodexProviderAdapter()
    limits = adapter.parse_usage(_profile(), result)
    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert limits[0].used_percent is None
    assert limits[0].window_label == "7-day"
