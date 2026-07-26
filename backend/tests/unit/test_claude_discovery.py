from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.vendor.claude_statusline import discovery


def _make_credible_dir(base: Path, name: str) -> Path:
    d = base / name
    d.mkdir()
    (d / "settings.json").write_text("{}", encoding="utf-8")
    return d


def test_default_and_home_candidates_discovered(tmp_path):
    _make_credible_dir(tmp_path, ".claude")
    _make_credible_dir(tmp_path, ".claude-work")

    profiles = discovery.discover_profiles(home=tmp_path)
    labels = {p.label for p in profiles}
    assert "default" in labels
    assert "work" in labels


def test_dedup_same_path_different_sources_keeps_highest_precedence(tmp_path, monkeypatch):
    d = _make_credible_dir(tmp_path, ".claude")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(d))

    profiles = discovery.discover_profiles(home=tmp_path)
    matching = [p for p in profiles if p.config_dir == d.resolve()]
    assert len(matching) == 1
    assert matching[0].source == discovery.SOURCE_DEFAULT  # default beats env:process


def test_insufficient_signals_rejected(tmp_path):
    d = tmp_path / ".claude-empty"
    d.mkdir()
    (d / "cache").mkdir()  # single weak signal only

    profiles = discovery.discover_profiles(home=tmp_path)
    assert all(p.config_dir != d.resolve() for p in profiles)


def test_include_invalid_surfaces_rejected_candidates(tmp_path):
    d = tmp_path / ".claude-empty"
    d.mkdir()
    (d / "cache").mkdir()

    profiles = discovery.discover_profiles(home=tmp_path, include_invalid=True)
    matching = [p for p in profiles if p.config_dir == d.resolve()]
    assert len(matching) == 1
    assert matching[0].valid is False


def test_safe_label_never_leaks_full_path(tmp_path):
    d = tmp_path / ".claude-secret-project"
    label = discovery.safe_label(d)
    assert label == "secret-project"
    assert str(tmp_path) not in label


def test_expand_powershell_path_rejects_unresolvable_dynamic_expr():
    # A bare, unresolved $env:/$-prefixed reference cannot be resolved safely.
    assert discovery.expand_powershell_path("$env:SOME_UNKNOWN_VAR") is None
    assert discovery.expand_powershell_path("$SomeUnknownVar") is None


def test_parse_powershell_profile_extracts_launcher_function():
    text = """
function claude-mt {
    $env:CLAUDE_CONFIG_DIR = "$HOME\\.claude-mt"
    claude @args
}
"""
    entries = discovery.parse_powershell_profile(text, home=Path("C:/Users/tester"))
    assert len(entries) == 1
    assert entries[0]["launcher"] == "claude-mt"
    assert entries[0]["config_dir"].endswith(".claude-mt")
