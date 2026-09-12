"""Builds sanitized diagnostics records for a profile."""

from __future__ import annotations

import json
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
        self._apply_latest_snapshot_context(profile_key, diag)
        return diag

    def _apply_latest_snapshot_context(
        self, profile_key: str, diag: ProfileDiagnostics
    ) -> None:
        rows = self._store.get_latest_snapshot_batch(profile_key)
        if not rows:
            return

        details = []
        for row in rows:
            try:
                details.append(json.loads(row.get("source_detail_json") or "{}"))
            except json.JSONDecodeError:
                details.append({})

        sources = [detail.get("source") for detail in details if detail.get("source")]
        if sources:
            source = str(sources[0])
            diag.parser_used = source
            diag.last_command_result = _source_summary(source)
            if diag.provider == "claude" and source == "claude_usage_command":
                diag.suggested_action = (
                    "Claude `/usage` live command returned parseable limit data for this profile."
                )

        reasons = [
            detail.get("usage_command_reason")
            for detail in details
            if detail.get("usage_command_reason")
        ]
        if reasons and diag.provider == "claude":
            diag.last_command_result = (
                f"Claude `/usage` ran but did not return parseable limits: {str(reasons[0])[:180]}"
            )


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


def _source_summary(source: str) -> str:
    summaries = {
        "claude_usage_command": "Claude `/usage` live command parsed current limit windows.",
        "claude_usage_notifier_db": "Claude notifier statusline DB supplied latest captured windows.",
        "codex_app_server_live_probe": "Codex app-server live probe returned account rate limits.",
        "antigravity_usage_snapshot": "Antigravity usage snapshot text file supplied quota windows.",
        "antigravity_usage_command": "Antigravity usage command parsed quota windows.",
        "free_ai_local_router_logs": "Free-AI local router logs supplied successful model request counts.",
        "free_ai_local_files": "Free-AI local config/env files were read without provider API calls.",
    }
    return summaries.get(source, source)
