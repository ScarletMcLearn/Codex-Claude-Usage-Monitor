from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.settings import SettingsPatch
from ...services.settings_service import SettingsService
from ..deps import get_settings_service

router = APIRouter()


@router.get("/settings")
def get_settings(settings_service: SettingsService = Depends(get_settings_service)) -> dict:
    return settings_service.get().model_dump(mode="json")


@router.patch("/settings")
def patch_settings(
    patch: SettingsPatch, settings_service: SettingsService = Depends(get_settings_service)
) -> dict:
    return settings_service.patch(patch).model_dump(mode="json")
