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
    agent: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
    repository: str | None = None,
    branch: str | None = None,
    worktree: str | None = None,
    session_id: str | None = None,
    token_quality: str | None = None,
    min_total_tokens: int | None = Query(None, ge=0),
    min_input_tokens: int | None = Query(None, ge=0),
    min_output_tokens: int | None = Query(None, ge=0),
    has_tools: bool = False,
    has_commands: bool = False,
    has_child_relationships: bool = False,
    since_utc: str | None = None,
    until_utc: str | None = None,
    service: ForensicsService = Depends(get_forensics_service),
):
    filters = {
        "agent": agent,
        "provider": provider,
        "model": model,
        "project": project,
        "repository": repository,
        "branch": branch,
        "worktree": worktree,
        "session_id": session_id,
        "token_quality": token_quality,
        "min_total_tokens": min_total_tokens,
        "min_input_tokens": min_input_tokens,
        "min_output_tokens": min_output_tokens,
        "has_tools": has_tools,
        "has_commands": has_commands,
        "has_child_relationships": has_child_relationships,
        "since_utc": since_utc,
        "until_utc": until_utc,
    }
    return service.sessions(limit=limit, offset=offset, filters=filters)


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
    session_id: str | None = None,
    agent: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
    since_utc: str | None = None,
    until_utc: str | None = None,
    service: ForensicsService = Depends(get_forensics_service),
):
    try:
        filters = {
            "session_id": session_id,
            "agent": agent,
            "provider": provider,
            "model": model,
            "project": project,
            "since_utc": since_utc,
            "until_utc": until_utc,
        }
        filters = {key: value for key, value in filters.items() if value}
        return service.export(export_type=export_type, warning_ack=warning_ack, filters=filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
