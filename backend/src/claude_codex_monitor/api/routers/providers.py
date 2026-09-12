from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/providers")
def list_providers() -> list[dict]:
    return [
        {"provider": "claude", "display_name": "Claude Code"},
        {"provider": "codex", "display_name": "Codex"},
        {"provider": "antigravity", "display_name": "Antigravity"},
        {"provider": "free_ai", "display_name": "Free-AI"},
    ]
