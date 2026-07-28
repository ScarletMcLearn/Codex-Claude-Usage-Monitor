from __future__ import annotations

from claude_codex_monitor.vendor.antigravity.usage_command import (
    AntigravityUsageCommandResult,
    parse_usage_output,
    read_usage_snapshot,
    run_usage_command,
)
from claude_codex_monitor.vendor.antigravity.models import AntigravityProfileCandidate


def test_parse_usage_output_explicit_model_percent():
    windows = parse_usage_output("Gemini 3.5 Flash: 64% used\nGemini 3.1 Pro: 22%", observed_utc=123.0)

    assert [(w.window_label, w.used_percentage) for w in windows] == [
        ("Gemini 3.5 Flash", 64.0),
        ("Gemini 3.1 Pro", 22.0),
    ]


def test_parse_usage_output_remaining_percent():
    windows = parse_usage_output("Gemini 3.5 Flash: 15% remaining", observed_utc=123.0)

    assert windows[0].window_label == "Gemini 3.5 Flash"
    assert windows[0].used_percentage == 85.0


def test_parse_usage_output_ignores_lines_without_percent():
    assert parse_usage_output("Quota refreshed successfully\nNo percentage here", observed_utc=123.0) == []


def test_parse_usage_output_antigravity_tui_groups():
    output = """
    └ Models & Quota

      Account: syed.elahi@allgentech.io

    GEMINI MODELS
      Models within this group: Gemini Flash, Gemini Pro

      Weekly Limit
        [██████████████████████████████████████████████████] 100.00%
        Quota available

    CLAUDE AND GPT MODELS
      Models within this group: Claude Opus, Claude Sonnet, GPT-OSS

      Weekly Limit
        [██████████████████████████████████████████████████] 100.00%
        Quota available
    """

    windows = parse_usage_output(output, observed_utc=123.0)

    assert [(w.window_label, w.used_percentage) for w in windows] == [
        ("Gemini Models: Weekly Limit", 0.0),
        ("Claude And Gpt Models: Weekly Limit", 0.0),
    ]


def test_run_usage_command_detects_print_mode_help(monkeypatch, tmp_path):
    profile = AntigravityProfileCandidate(
        label="default",
        kind="default home",
        config_home=tmp_path,
        executable=tmp_path / "agy.exe",
    )

    class Completed:
        returncode = 0
        stdout = (
            '{"response":"Type `/usage` directly inside the CLI interface to view quota.",'
            '"usage":{"input_tokens":1,"output_tokens":2,"thinking_tokens":0,'
            '"cache_read_tokens":0,"total_tokens":3}}'
        )
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr("claude_codex_monitor.vendor.antigravity.usage_command._probe_cwd", lambda: tmp_path)

    result = run_usage_command(profile)

    assert isinstance(result, AntigravityUsageCommandResult)
    assert result.ok is True
    assert result.windows == []
    assert "print mode treated `/usage`" in result.reason


def test_read_usage_snapshot_parses_manual_panel(monkeypatch, tmp_path):
    snapshot = tmp_path / "usage.txt"
    snapshot.write_text(
        "GEMINI MODELS\n"
        "  Weekly Limit\n"
        "    [██████████████████████████████████████████████████] 100.00%\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CCM_ANTIGRAVITY_USAGE_SNAPSHOT", str(snapshot))

    result = read_usage_snapshot()

    assert result is not None
    assert result.ok is True
    assert result.windows[0].window_label == "Gemini Models: Weekly Limit"
    assert result.windows[0].used_percentage == 100.0
