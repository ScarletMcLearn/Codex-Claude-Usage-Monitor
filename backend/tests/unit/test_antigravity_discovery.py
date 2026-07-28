from __future__ import annotations

from pathlib import Path

from claude_codex_monitor.vendor.antigravity import discovery


def test_credible_home_requires_signal_file(tmp_path):
    home = tmp_path / ".gemini" / "antigravity-cli"
    home.mkdir(parents=True)
    assert discovery.credible_home(home) is False
    (home / "settings.json").write_text("{}", encoding="utf-8")
    assert discovery.credible_home(home) is True


def test_default_cli_home_discovered(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    home = tmp_path / ".gemini" / "antigravity-cli"
    home.mkdir(parents=True)
    (home / "settings.json").write_text("{}", encoding="utf-8")

    profiles = discovery.discover_profiles()

    assert any(p.label == "default" and p.kind == "default home" for p in profiles)


def test_project_discovered_as_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    projects = tmp_path / ".gemini" / "config" / "projects"
    projects.mkdir(parents=True)
    (projects / "work.json").write_text('{"id":"work","name":"Work"}', encoding="utf-8")

    profiles = discovery.discover_profiles()

    project = next(p for p in profiles if p.label == "Work")
    assert project.project_id == "work"
    assert project.kind == "project"
