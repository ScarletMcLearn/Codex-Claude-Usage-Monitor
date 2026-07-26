from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...services.diagnostics_service import DiagnosticsService
from ..deps import get_diagnostics_service

router = APIRouter()


@router.get("/diagnostics/{profile_key}")
def get_diagnostics(
    profile_key: str, diagnostics_service: DiagnosticsService = Depends(get_diagnostics_service)
) -> dict:
    diag = diagnostics_service.diagnose(profile_key)
    if diag is None:
        raise HTTPException(status_code=404, detail="Unknown profile")
    return diag.model_dump(mode="json")
