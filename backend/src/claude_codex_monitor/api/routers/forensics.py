from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...services.forensics_service import ForensicsService
from ..deps import get_forensics_service

router = APIRouter(tags=["forensics"])


@router.post("/forensics/refresh")
def refresh_forensics(service: ForensicsService = Depends(get_forensics_service)):
    return service.refresh()


@router.get("/forensics/overview")
def forensic_overview(service: ForensicsService = Depends(get_forensics_service)):
    return service.overview()


@router.get("/forensics/sessions")
def forensic_sessions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: ForensicsService = Depends(get_forensics_service),
):
    return service.sessions(limit=limit, offset=offset)


@router.get("/forensics/sessions/{session_id}")
def forensic_session(session_id: str, service: ForensicsService = Depends(get_forensics_service)):
    detail = service.session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="forensic session not found")
    return detail


@router.get("/forensics/turns/{turn_id}")
def forensic_turn(turn_id: str, service: ForensicsService = Depends(get_forensics_service)):
    detail = service.turn_detail(turn_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="forensic turn not found")
    return detail


@router.get("/forensics/hotspots")
def forensic_hotspots(service: ForensicsService = Depends(get_forensics_service)):
    return service.hotspots()


@router.post("/forensics/export")
def forensic_export(
    export_type: str = Query("summary", pattern="^(summary|full)$"),
    warning_ack: bool = Query(False),
    service: ForensicsService = Depends(get_forensics_service),
):
    try:
        return service.export(export_type=export_type, warning_ack=warning_ack)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
