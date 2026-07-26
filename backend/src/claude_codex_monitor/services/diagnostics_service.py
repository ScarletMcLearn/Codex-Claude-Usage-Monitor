"""Builds sanitized diagnostics records for a profile."""

from __future__ import annotations

from datetime import UTC

from ..db.store import Store
from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus
from ..services.discovery_service import DiscoveryService


class DiagnosticsService:
    def __init__(self, store: Store, discovery_service: DiscoveryService) -> None:
        self._store = store
        self._discovery = discovery_service

    def diagnose(self, profile_key: str) -> ProfileDiagnostics | None:
        row = self._store.get_profile(profile_key)
        if row is None:
            return None
        profile = ProfileStatus(
            provider=row["provider"],
            profile_id=row["profile_id"],
            profile_key=row["profile_key"],
            label=row["label"],
            friendly_name=row.get("friendly_name"),
            sanitized_source=row["sanitized_source"],
            discovery_source=row["discovery_source"],
            is_active=bool(row["is_active"]),
            last_error=row.get("last_error"),
        )
        adapter = self._discovery.adapters.get(profile.provider)
        if adapter is None:
            return None
        diag = adapter.diagnose_error(profile, row.get("last_error") or "")
        diag.last_successful_query_utc = _parse(row.get("last_success_utc"))
        return diag


def _parse(value):
    if not value:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
