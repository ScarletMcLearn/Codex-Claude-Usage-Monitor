"""Runs provider discovery and syncs results into the profiles table."""

from __future__ import annotations

import logging
from datetime import UTC

from ..adapters.antigravity_adapter import AntigravityProviderAdapter
from ..adapters.base import ProviderAdapter
from ..adapters.claude_adapter import ClaudeProviderAdapter
from ..adapters.codex_adapter import CodexProviderAdapter
from ..db.store import Store
from ..models.profile import ProfileStatus

LOGGER = logging.getLogger("claude_codex_monitor.services.discovery")


class DiscoveryService:
    def __init__(
        self,
        store: Store,
        claude_adapter: ProviderAdapter | None = None,
        codex_adapter: ProviderAdapter | None = None,
        antigravity_adapter: ProviderAdapter | None = None,
    ) -> None:
        self._store = store
        self.claude_adapter: ProviderAdapter = claude_adapter or ClaudeProviderAdapter()
        self.codex_adapter: ProviderAdapter = codex_adapter or CodexProviderAdapter()
        self.antigravity_adapter: ProviderAdapter = antigravity_adapter or AntigravityProviderAdapter()

    @property
    def adapters(self) -> dict[str, ProviderAdapter]:
        return {
            "claude": self.claude_adapter,
            "codex": self.codex_adapter,
            "antigravity": self.antigravity_adapter,
        }

    def discover_all(self) -> list[ProfileStatus]:
        discovered: list[ProfileStatus] = []
        for provider_name, adapter in self.adapters.items():
            try:
                profiles = adapter.discover_profiles()
            except Exception as exc:  # noqa: BLE001 - discovery must never crash the app
                LOGGER.warning("Discovery failed for provider %s: %s", provider_name, exc)
                continue
            for profile in profiles:
                self._store.upsert_profile(
                    provider=profile.provider,
                    profile_id=profile.profile_id,
                    label=profile.label,
                    sanitized_source=profile.sanitized_source,
                    discovery_source=profile.discovery_source,
                )
                discovered.append(profile)
        return discovered

    def list_profiles(self) -> list[ProfileStatus]:
        rows = self._store.get_profiles()
        results = []
        for row in rows:
            results.append(
                ProfileStatus(
                    provider=row["provider"],
                    profile_id=row["profile_id"],
                    profile_key=row["profile_key"],
                    label=row["label"],
                    friendly_name=row.get("friendly_name"),
                    sanitized_source=row["sanitized_source"],
                    discovery_source=row["discovery_source"],
                    is_active=bool(row["is_active"]),
                    last_refresh_utc=_parse(row.get("last_refresh_utc")),
                    last_success_utc=_parse(row.get("last_success_utc")),
                    last_error=row.get("last_error"),
                    is_stale=_is_stale(row.get("last_success_utc")),
                )
            )
        return results


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


def _is_stale(last_success_utc: str | None) -> bool:
    if not last_success_utc:
        return False
    from datetime import datetime, timedelta

    dt = _parse(last_success_utc)
    if dt is None:
        return False
    return datetime.now(UTC) - dt > timedelta(hours=6)
