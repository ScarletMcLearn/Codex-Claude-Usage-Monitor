"""Settings persistence: single JSON blob under one settings key, KV table."""

from __future__ import annotations

import json

from ..db.store import Store
from ..models.settings import Settings, SettingsPatch

_KEY = "app_settings"


class SettingsService:
    def __init__(self, store: Store) -> None:
        self._store = store

    def get(self) -> Settings:
        raw = self._store.get_setting(_KEY)
        if not raw:
            return Settings()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return Settings()
        return Settings.model_validate(data)

    def patch(self, patch: SettingsPatch) -> Settings:
        current = self.get()
        updates = patch.model_dump(exclude_unset=True, exclude_none=True)
        merged = current.model_copy(update=updates)
        self._store.set_setting(_KEY, merged.model_dump_json())
        return merged
