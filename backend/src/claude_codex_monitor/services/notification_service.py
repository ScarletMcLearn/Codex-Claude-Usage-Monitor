"""Windows notifications for this dashboard, with cooldown/dedup.

Uses win11toast when available; degrades to a no-op with a clear log line
otherwise (never blocks the rest of the app).
"""

from __future__ import annotations

import logging

from ..db.store import Store
from ..models.settings import Settings
from ..models.usage import DataQuality, UsageLimit

LOGGER = logging.getLogger("claude_codex_monitor.services.notification")

try:
    from win11toast import toast as _toast  # type: ignore[import-not-found]

    _TOAST_AVAILABLE = True
except ImportError:
    _TOAST_AVAILABLE = False

    def _toast(*args, **kwargs):  # type: ignore[no-redef]
        return None


class NotificationService:
    def __init__(self, store: Store) -> None:
        self._store = store
        if not _TOAST_AVAILABLE:
            LOGGER.info("win11toast not installed; Windows notifications disabled (no-op).")

    def _send(
        self,
        title: str,
        message: str,
        dedupe_key: str,
        *,
        profile_key: str,
        window_id: str,
        event_type: str,
    ) -> None:
        if self._store.was_notification_sent(dedupe_key):
            return
        sent = self._store.mark_notification_sent(
            dedupe_key, profile_key=profile_key, window_id=window_id, event_type=event_type
        )
        if not sent:
            return
        if _TOAST_AVAILABLE:
            try:
                _toast(title, message)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Toast notification failed: %s", exc)
        else:
            LOGGER.info("[notification suppressed - win11toast unavailable] %s: %s", title, message)

    def evaluate_usage(
        self, settings: Settings, profile_key: str, profile_label: str, limit: UsageLimit
    ) -> None:
        if not settings.notifications_enabled:
            return
        reset_part = limit.resets_at_utc.isoformat() if limit.resets_at_utc else "no-reset"

        if limit.quality == DataQuality.UNAVAILABLE and "auth" in (limit.unavailable_reason or "").lower():
            if settings.notify_on_auth_required:
                key = f"{profile_key}|{limit.window_id}|auth_required"
                self._send(
                    "Authentication required",
                    f"{profile_label} ({limit.window_label}) needs re-authentication.",
                    key,
                    profile_key=profile_key,
                    window_id=limit.window_id,
                    event_type="auth_required",
                )
            return

        if limit.used_percent is None or limit.quality not in (DataQuality.VERIFIED, DataQuality.DERIVED):
            return

        pct = limit.used_percent
        if pct >= 100 and settings.notify_on_exhaustion:
            key = f"{profile_key}|{limit.window_id}|{reset_part}|exhausted"
            self._send(
                "Usage limit exhausted",
                f"{profile_label} ({limit.window_label}) has reached 100% usage.",
                key,
                profile_key=profile_key,
                window_id=limit.window_id,
                event_type="exhausted",
            )
        elif pct >= 95 and settings.notify_at_95_percent:
            key = f"{profile_key}|{limit.window_id}|{reset_part}|95"
            self._send(
                "Usage critical (95%+)",
                f"{profile_label} ({limit.window_label}) is at {pct:.0f}% usage.",
                key,
                profile_key=profile_key,
                window_id=limit.window_id,
                event_type="usage_95",
            )
        elif pct >= 80 and settings.notify_at_80_percent:
            key = f"{profile_key}|{limit.window_id}|{reset_part}|80"
            self._send(
                "Usage high (80%+)",
                f"{profile_label} ({limit.window_label}) is at {pct:.0f}% usage.",
                key,
                profile_key=profile_key,
                window_id=limit.window_id,
                event_type="usage_80",
            )

    def notify_reset_completed(
        self,
        settings: Settings,
        profile_key: str,
        profile_label: str,
        window_id: str,
        window_label: str,
        reset_at_iso: str,
    ) -> None:
        if not settings.notifications_enabled or not settings.notify_on_reset:
            return
        key = f"{profile_key}|{window_id}|{reset_at_iso}|reset_completed"
        self._send(
            "Usage reset",
            f"{profile_label} ({window_label}) usage window has reset.",
            key,
            profile_key=profile_key,
            window_id=window_id,
            event_type="reset_completed",
        )

    def notify_repeated_failures(
        self, settings: Settings, profile_key: str, profile_label: str, failure_count: int
    ) -> None:
        if not settings.notifications_enabled or not settings.notify_on_repeated_failures:
            return
        if failure_count not in (3, 10, 25):  # avoid spamming on every single failure
            return
        key = f"{profile_key}|repeated_failures|{failure_count}"
        self._send(
            "Repeated refresh failures",
            f"{profile_label} has failed to refresh {failure_count} times in a row.",
            key,
            profile_key=profile_key,
            window_id="unknown",
            event_type="repeated_failures",
        )
