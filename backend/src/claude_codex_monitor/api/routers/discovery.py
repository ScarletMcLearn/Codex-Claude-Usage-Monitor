from __future__ import annotations

from fastapi import APIRouter, Depends

from ...services.discovery_service import DiscoveryService
from ..deps import get_discovery_service

router = APIRouter()


@router.post("/discovery/refresh")
def refresh_discovery(discovery_service: DiscoveryService = Depends(get_discovery_service)) -> dict:
    profiles = discovery_service.discover_all()
    return {"discovered": len(profiles)}
