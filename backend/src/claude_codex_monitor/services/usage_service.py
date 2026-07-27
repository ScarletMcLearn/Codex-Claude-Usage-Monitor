"""Orchestrates fetch -> parse -> persist -> notify for one or all profiles."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any

from ..db.store import Store
from ..models.profile import ProfileStatus
from ..models.usage import DataQuality, UsageLimit
from ..services.discovery_service import DiscoveryService
from ..services.history_service import HistoryService
from ..services.notification_service import NotificationService
from ..services.settings_service import SettingsService

LOGGER = logging.getLogger("claude_codex_monitor.services.usage")

# In-memory consecutive-failure counters, keyed by profile_key. Not persisted -
# resets on process restart, which is fine since it only drives notification
# de-dup thresholds, not correctness.
_consecutive_failures: dict[str, int] = {}


class UsageService:
    def __init__(
        self,
        store: Store,
        discovery_service: DiscoveryService,
        history_service: HistoryService,
        settings_service: SettingsService,
        notification_service: NotificationService,
    ) -> None:
        self._store = store
        self._discovery = discovery_service
        self._history = history_service
        self._settings = settings_service
        self._notifications = notification_service

    def refresh_profile(self, profile_key: str) -> list[UsageLimit]:
        row = self._store.get_profile(profile_key)
        if row is None:
            raise KeyError(f"Unknown profile: {profile_key}")
        profile = ProfileStatus(
            provider=row["provider"],
            profile_id=row["profile_id"],
            profile_key=row["profile_key"],
            label=row["label"],
            friendly_name=row.get("friendly_name"),
            sanitized_source=row["sanitized_source"],
            discovery_source=row["discovery_source"],
            is_active=bool(row["is_active"]),
        )
        adapter = self._discovery.adapters.get(profile.provider)
        if adapter is None:
            raise KeyError(f"No adapter for provider {profile.provider}")

        settings = self._settings.get()
        display_label = profile.friendly_name or profile.label

        try:
            raw = adapter.fetch_usage(profile)
            limits = adapter.parse_usage(profile, raw)
        except Exception as exc:  # noqa: BLE001 - never let one profile crash refresh-all
            LOGGER.warning("fetch/parse failed for %s: %s", profile_key, exc)
            _consecutive_failures[profile_key] = _consecutive_failures.get(profile_key, 0) + 1
            self._store.set_profile_refresh_result(profile_key, success=False, error=str(exc)[:300])
            self._notifications.notify_repeated_failures(
                settings, profile_key, display_label, _consecutive_failures[profile_key]
            )
            limits = [
                UsageLimit(
                    provider=profile.provider,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason=f"Refresh failed: {exc}"[:300],
                    observed_at_utc=_now(),
                )
            ]
            return limits

        any_unavailable_only = all(item.quality == DataQuality.UNAVAILABLE for item in limits)
        if any_unavailable_only:
            _consecutive_failures[profile_key] = _consecutive_failures.get(profile_key, 0) + 1
        else:
            _consecutive_failures[profile_key] = 0
        self._store.set_profile_refresh_result(profile_key, success=not any_unavailable_only)

        for limit in limits:
            self._history.record(profile_key, limit)
            self._notifications.evaluate_usage(settings, profile_key, display_label, limit)

        if any_unavailable_only:
            self._notifications.notify_repeated_failures(
                settings, profile_key, display_label, _consecutive_failures[profile_key]
            )

        return limits

    def refresh_all(self) -> dict[str, list[UsageLimit]]:
        results: dict[str, list[UsageLimit]] = {}
        for profile in self._discovery.list_profiles():
            if not profile.is_active:
                continue
            try:
                results[profile.profile_key] = self.refresh_profile(profile.profile_key)
            except KeyError as exc:
                LOGGER.warning("Skipping profile during refresh_all: %s", exc)
        settings = self._settings.get()
        self._history.maybe_apply_retention(settings.history_retention_days)
        return results

    def get_current_limits(self, profile_key: str) -> list[UsageLimit]:
        """Return the latest known reading per window for a profile, without
        forcing a new fetch (used by GET endpoints)."""
        rows = self._store.get_history(profile_key=profile_key, limit=1000)
        if not rows:
            return []

        latest_observed = max(row["observed_at_utc"] for row in rows)
        return [_row_to_usage_limit(row) for row in rows if row["observed_at_utc"] == latest_observed]


def _row_to_usage_limit(row: dict[str, Any]) -> UsageLimit:
    import json
    from datetime import datetime

    def parse_dt(value):
        if not value:
            return None
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def window_label() -> str:
        label = row.get("window_label") or row["window_id"]
        if row.get("provider") == "codex":
            if row["window_id"] == "primary" or label in ("Primary", "1 week"):
                return "7-day"
            if row["window_id"] == "secondary" or label in ("Secondary", "5h"):
                return "5-hour"
        return label

    return UsageLimit(
        provider=row["provider"],
        profile_id=row["profile_key"].split(":", 1)[1] if ":" in row["profile_key"] else row["profile_key"],
        window_id=row["window_id"],
        window_label=window_label(),
        used_percent=row.get("used_percent"),
        remaining_percent=row.get("remaining_percent"),
        resets_at_utc=parse_dt(row.get("resets_at_utc")),
        reset_confirmed=bool(row.get("reset_confirmed")),
        quality=row["quality"],
        unavailable_reason=row.get("unavailable_reason"),
        observed_at_utc=parse_dt(row["observed_at_utc"]) or datetime.now(UTC),
        source_detail=json.loads(row["source_detail_json"]) if row.get("source_detail_json") else {},
    )


def _now():
    from datetime import datetime

    return datetime.now(UTC)
