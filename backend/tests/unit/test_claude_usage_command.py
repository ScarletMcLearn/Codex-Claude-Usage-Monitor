from __future__ import annotations

from datetime import UTC

from claude_codex_monitor.vendor.claude_usage_command import parse_usage_output


def test_parse_usage_output_explicit_window_percent():
    windows = parse_usage_output("5-hour limit: 84%\n7-day limit: 33%", observed_utc=123.0)
    assert [(window.window_name, window.used_percentage) for window in windows] == [
        ("five_hour", 84.0),
        ("seven_day", 33.0),
    ]


def test_parse_usage_output_remaining_percent():
    windows = parse_usage_output("5h: 16% remaining", observed_utc=123.0)
    assert windows[0].window_name == "five_hour"
    assert windows[0].used_percentage == 84.0


def test_parse_usage_output_fully_used():
    windows = parse_usage_output("5-hour fully used", observed_utc=123.0)
    assert windows[0].used_percentage == 100.0


def test_parse_usage_output_current_session_and_week():
    windows = parse_usage_output(
        "Current session: 11% used - resets Jul 27, 2:09pm\n"
        "Current week (all models): 2% used - resets Aug 3, 10am",
        observed_utc=1785139200.0,
    )
    assert [(window.window_name, window.used_percentage) for window in windows] == [
        ("five_hour", 11.0),
        ("seven_day", 2.0),
    ]
    assert windows[0].resets_at_utc is not None
    assert windows[0].resets_at_utc.astimezone(UTC).isoformat() == "2026-07-27T08:09:00+00:00"


def test_parse_usage_output_does_not_guess_from_contributor_percentages():
    output = """
    Last 24h - 679 requests - 6 sessions
      77% of your usage came from subagent-heavy sessions
    Last 7d - 2230 requests - 20 sessions
      63% of your usage was at >150k context
    """
    assert parse_usage_output(output, observed_utc=123.0) == []
