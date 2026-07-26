from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ...services.history_service import HistoryService
from ..deps import get_history_service

router = APIRouter()

_VALID_RANGES = {"today", "7d", "30d", "90d", "all"}


@router.get("/history")
def get_history(
    provider: str | None = Query(default=None),
    profile_key: str | None = Query(default=None),
    window_id: str | None = Query(default=None),
    range: str = Query(default="7d"),  # noqa: A002
    history_service: HistoryService = Depends(get_history_service),
) -> list[dict]:
    if range not in _VALID_RANGES:
        raise HTTPException(status_code=400, detail=f"range must be one of {sorted(_VALID_RANGES)}")
    rows = history_service.query(
        provider=provider, profile_key=profile_key, window_id=window_id, range_key=range
    )
    return rows


@router.delete("/history")
def delete_history(
    confirm: bool = Query(default=False),
    body: dict | None = Body(default=None),
    history_service: HistoryService = Depends(get_history_service),
) -> dict:
    body_confirm = bool((body or {}).get("confirm"))
    if not (confirm or body_confirm):
        raise HTTPException(
            status_code=400,
            detail="Explicit confirm=true (query param or body field) is required to delete history.",
        )
    deleted = history_service.delete_all(confirmed=True)
    return {"deleted": deleted}
