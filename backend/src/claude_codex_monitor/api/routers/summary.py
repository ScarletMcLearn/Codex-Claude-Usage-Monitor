from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ...models.usage import DataQuality
from ...services.discovery_service import DiscoveryService
from ...services.usage_service import UsageService
from ..deps import get_discovery_service, get_usage_service

router = APIRouter()


@router.get("/summary")
def get_summary(
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    usage_service: UsageService = Depends(get_usage_service),
) -> dict:
    profiles = discovery_service.list_profiles()
    total = len(profiles)
    queried_ok = 0
    need_auth = 0
    stale_or_failed = 0
    over_80 = 0
    over_95 = 0
    next_reset: datetime | None = None

    for profile in profiles:
        limits = usage_service.get_current_limits(profile.profile_key)
        profile_ok = False
        for limit in limits:
            if limit.quality in (DataQuality.VERIFIED, DataQuality.DERIVED):
                profile_ok = True
                if limit.used_percent is not None:
                    if limit.used_percent >= 95:
                        over_95 += 1
                    elif limit.used_percent >= 80:
                        over_80 += 1
                if limit.resets_at_utc and (next_reset is None or limit.resets_at_utc < next_reset):
                    next_reset = limit.resets_at_utc
            elif limit.quality == DataQuality.UNAVAILABLE and "auth" in (limit.unavailable_reason or "").lower():
                need_auth += 1
        if profile_ok:
            queried_ok += 1
        if profile.is_stale or profile.last_error:
            stale_or_failed += 1

    return {
        "total_profiles": total,
        "queried_successfully": queried_ok,
        "need_auth": need_auth,
        "over_80_percent": over_80,
        "over_95_percent": over_95,
        "next_reset_utc": next_reset.isoformat() if next_reset else None,
        "stale_or_failed": stale_or_failed,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
