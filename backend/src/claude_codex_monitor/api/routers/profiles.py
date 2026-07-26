from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...services.discovery_service import DiscoveryService
from ...services.usage_service import UsageService
from ..deps import get_discovery_service, get_usage_service

router = APIRouter()


class FriendlyNamePatch(BaseModel):
    friendly_name: str | None = None


@router.get("/profiles")
def list_profiles(
    discovery_service: DiscoveryService = Depends(get_discovery_service),
) -> list[dict]:
    return [p.model_dump(mode="json") for p in discovery_service.list_profiles()]


@router.post("/profiles/{profile_key}/refresh")
def refresh_profile(
    profile_key: str, usage_service: UsageService = Depends(get_usage_service)
) -> dict:
    try:
        limits = usage_service.refresh_profile(profile_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "profile_key": profile_key,
        "limits": [limit.model_dump(mode="json") for limit in limits],
    }


@router.get("/profiles/{profile_id}/limits")
def get_profile_limits(
    profile_id: str, usage_service: UsageService = Depends(get_usage_service)
) -> list[dict]:
    limits = usage_service.get_current_limits(profile_id)
    return [limit.model_dump(mode="json") for limit in limits]


@router.post("/refresh-all")
def refresh_all(usage_service: UsageService = Depends(get_usage_service)) -> dict:
    results = usage_service.refresh_all()
    return {
        "profiles_refreshed": len(results),
        "results": {
            key: [limit.model_dump(mode="json") for limit in limits]
            for key, limits in results.items()
        },
    }
