from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.adapters.antigravity_adapter import AntigravityProviderAdapter
from claude_codex_monitor.models.profile import ProfileStatus
from claude_codex_monitor.models.usage import DataQuality
from claude_codex_monitor.vendor.antigravity.models import AntigravityProfileCandidate
from claude_codex_monitor.vendor.antigravity.usage_command import AntigravityUsageCommandWindow


def test_unavailable_usage_is_explicit():
    adapter = AntigravityProviderAdapter()
    profile = ProfileStatus(
        provider="antigravity",
        profile_id="p",
        profile_key="antigravity:p",
        label="default",
        sanitized_source="~/.gemini/antigravity-cli",
        discovery_source="default cli home",
    )

    limits = adapter.parse_usage(profile, {"ok": False, "error": "no quota endpoint"})

    assert limits[0].quality == DataQuality.UNAVAILABLE
    assert "no quota endpoint" in limits[0].unavailable_reason


def test_usage_command_windows_are_verified():
    adapter = AntigravityProviderAdapter()
    profile = ProfileStatus(
        provider="antigravity",
        profile_id="p",
        profile_key="antigravity:p",
        label="default",
        sanitized_source="~/.gemini/antigravity-cli",
        discovery_source="default cli home",
    )

    limits = adapter.parse_usage(
        profile,
        {
            "ok": True,
            "windows": [
                AntigravityUsageCommandWindow("gemini_3_5_flash", "Gemini 3.5 Flash", 64.0, 123.0)
            ],
        },
    )

    assert limits[0].quality == DataQuality.VERIFIED
    assert limits[0].used_percent == 64.0
    assert limits[0].remaining_percent == 36.0
    assert limits[0].source_detail["source"] == "antigravity_usage_command"


def test_diagnostics_point_to_usage_command():
    adapter = AntigravityProviderAdapter()
    profile = ProfileStatus(
        provider="antigravity",
        profile_id="p",
        profile_key="antigravity:p",
        label="default",
        sanitized_source="~/.gemini/antigravity-cli",
        discovery_source="default cli home",
    )

    diag = adapter.diagnose_error(profile, "")

    assert diag.parser_used == "antigravity_usage_command"
    assert "`/usage`" in diag.suggested_action
    assert "not used by default" in diag.suggested_action


def test_fetch_usage_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CCM_ANTIGRAVITY_USAGE_COMMAND", raising=False)
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(Path("does-not-exist")))
    adapter = AntigravityProviderAdapter()
    profile = ProfileStatus(
        provider="antigravity",
        profile_id="p",
        profile_key="antigravity:p",
        label="default",
        sanitized_source="~/.gemini/antigravity-cli",
        discovery_source="default cli home",
    )
    adapter._candidates_by_id = {
        "p": AntigravityProfileCandidate(
            label="default",
            kind="default home",
            config_home=Path("unused"),
            executable=Path("agy"),
        )
    }

    raw = adapter.fetch_usage(profile)

    assert raw["ok"] is False
    assert "Put copied `/usage` panel text" in raw["error"]


def test_fetch_usage_prefers_manual_snapshot(monkeypatch, tmp_path):
    snapshot = tmp_path / "usage.txt"
    snapshot.write_text(
        "GEMINI MODELS\n"
        "  Weekly Limit\n"
        "    [██████████████████████████████████████████████████] 100.00%\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(snapshot))
    adapter = AntigravityProviderAdapter()
    profile = ProfileStatus(
        provider="antigravity",
        profile_id="p",
        profile_key="antigravity:p",
        label="default",
        sanitized_source="~/.gemini/antigravity-cli",
        discovery_source="default cli home",
    )
    adapter._candidates_by_id = {
        "p": AntigravityProfileCandidate(
            label="default",
            kind="default home",
            config_home=Path("unused"),
            executable=None,
        )
    }

    raw = adapter.fetch_usage(profile)
    limits = adapter.parse_usage(profile, raw)

    assert raw["source"] == "antigravity_usage_snapshot"
    assert limits[0].quality == DataQuality.VERIFIED
    assert limits[0].used_percent == 100.0
