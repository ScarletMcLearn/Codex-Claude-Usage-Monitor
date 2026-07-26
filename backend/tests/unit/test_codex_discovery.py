from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.vendor.codex_appserver import discovery


def test_credible_home_requires_signal_file(tmp_path):
    home = tmp_path / ".codex"
    home.mkdir()
    assert discovery.credible_home(home) is False
    (home / "config.toml").write_text("", encoding="utf-8")
    assert discovery.credible_home(home) is True


def test_credible_home_missing_dir_is_false(tmp_path):
    assert discovery.credible_home(tmp_path / "does-not-exist") is False


def test_named_config_profile_discovered(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    home = tmp_path / ".codex"
    home.mkdir()
    (home / "config.toml").write_text("", encoding="utf-8")
    (home / "work.config.toml").write_text("", encoding="utf-8")

    profiles = discovery.discover_profiles()
    labels = {p.label for p in profiles}
    assert "default" in labels
    assert "default:work" in labels
    work = next(p for p in profiles if p.label == "default:work")
    assert work.profile_arg == "work"
