from __future__ import annotations

from claude_codex_monitor.models.settings import SettingsPatch
from claude_codex_monitor.services.settings_service import SettingsService


def test_default_settings(store):
    svc = SettingsService(store)
    settings = svc.get()
    assert settings.display_timezone == "Asia/Dhaka"
    assert settings.auto_refresh_enabled is True


def test_patch_merges_only_provided_fields(store):
    svc = SettingsService(store)
    svc.patch(SettingsPatch(theme="dark"))
    updated = svc.get()
    assert updated.theme == "dark"
    assert updated.auto_refresh_enabled is True  # untouched


def test_patch_persists_across_instances(store):
    SettingsService(store).patch(SettingsPatch(refresh_interval_seconds=600))
    reloaded = SettingsService(store).get()
    assert reloaded.refresh_interval_seconds == 600
