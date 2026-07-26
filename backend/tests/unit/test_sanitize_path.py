from __future__ import annotations

from claude_codex_monitor.models.profile import sanitize_path


def test_home_prefix_replaced():
    import os

    home = os.path.expanduser("~")
    result = sanitize_path(home + "\\.claude-mt")
    assert result.startswith("~")
    assert home not in result


def test_users_segment_masked_even_without_home_match():
    result = sanitize_path(r"D:\Users\someoneelse\.claude")
    assert "someoneelse" not in result
    assert "<user>" in result
