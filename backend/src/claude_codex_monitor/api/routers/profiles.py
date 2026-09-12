from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...models.usage import DataQuality
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


@router.post("/usage-report")
def usage_report(
    discovery_service: DiscoveryService = Depends(get_discovery_service),
) -> dict:
    """Query each provider and return a report without persisting.

    Codex supports a live usage probe through `codex app-server --stdio`.
    Claude is probed through `/usage`; if that output has no parseable
    5-hour/7-day percentages, the report falls back to the latest statusline
    payload captured by the notifier DB. Antigravity profiles are discovered,
    but automatic print-mode `/usage` probing is disabled by default because
    it creates normal Antigravity turns instead of opening the slash panel.
    Free-AI is passive: local config/env/log reads only, no provider calls.
    """

    profiles = discovery_service.discover_all()
    rows = []
    for profile in profiles:
        if not profile.is_active:
            continue
        adapter = discovery_service.adapters.get(profile.provider)
        if adapter is None:
            rows.append(
                {
                    "profile_key": profile.profile_key,
                    "provider": profile.provider,
                    "label": profile.label,
                    "ok": False,
                    "source": "none",
                    "message": f"No adapter for provider {profile.provider}.",
                    "limits": [],
                }
            )
            continue

        source = {
            "claude": "claude /usage live command",
            "codex": "codex app-server live probe",
            "antigravity": "antigravity /usage live command",
            "free_ai": "free-ai local logs",
        }.get(profile.provider, f"{profile.provider} live probe")

        try:
            raw = adapter.fetch_usage(profile)
            limits = adapter.parse_usage(profile, raw)
            ok = any(limit.quality in (DataQuality.VERIFIED, DataQuality.DERIVED) for limit in limits)
            if profile.provider == "claude" and raw.get("source") == "claude_usage_notifier_db":
                source = "claude /usage live command + statusline fallback"
                command = raw.get("usage_command")
                command_reason = getattr(command, "reason", None)
                message = (
                    command_reason
                    or "Claude `/usage` did not return parseable limits; using statusline snapshot."
                )
            else:
                message = (
                    "Live provider query completed."
                    if ok
                    else "Provider query returned no verified usage."
                )
            rows.append(
                {
                    "profile_key": profile.profile_key,
                    "provider": profile.provider,
                    "label": profile.label,
                    "ok": ok,
                    "source": source,
                    "message": message,
                    "limits": [limit.model_dump(mode="json") for limit in limits],
                }
            )
        except Exception as exc:  # noqa: BLE001 - report all profiles even if one probe fails
            rows.append(
                {
                    "profile_key": profile.profile_key,
                    "provider": profile.provider,
                    "label": profile.label,
                    "ok": False,
                    "source": source,
                    "message": f"Usage probe failed: {str(exc)[:300]}",
                    "limits": [],
                }
            )

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "profiles_checked": len(rows),
        "rows": rows,
    }
