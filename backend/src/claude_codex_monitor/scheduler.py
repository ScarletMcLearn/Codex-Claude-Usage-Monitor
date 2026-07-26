"""Background refresh scheduler: asyncio task in the FastAPI lifespan.

- Discover at startup, refresh shortly after.
- Refresh periodically (configurable interval).
- No overlapping refreshes (single lock).
- Retry transient failures with backoff; do NOT tightly retry auth failures
  (those get a long fixed recheck interval instead).
- Save successful readings to history (via UsageService, already wired).
"""

from __future__ import annotations

import asyncio
import logging
import random

from .services.discovery_service import DiscoveryService
from .services.settings_service import SettingsService
from .services.usage_service import UsageService

LOGGER = logging.getLogger("claude_codex_monitor.scheduler")

_STARTUP_DISCOVERY_DELAY = 0.5
_STARTUP_REFRESH_DELAY = 5.0
_MAX_BACKOFF_SECONDS = 900  # 15 minutes cap for transient-failure backoff
_AUTH_RECHECK_SECONDS = 1800  # 30 minutes for profiles stuck needing auth


class RefreshScheduler:
    def __init__(
        self,
        discovery_service: DiscoveryService,
        usage_service: UsageService,
        settings_service: SettingsService,
    ) -> None:
        self._discovery = discovery_service
        self._usage = usage_service
        self._settings = settings_service
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._backoff_seconds = 0
        self.last_refresh_ok: bool | None = None

    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="ccm-refresh-scheduler")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        await asyncio.sleep(_STARTUP_DISCOVERY_DELAY)
        await self._safe_discover()

        await asyncio.sleep(_STARTUP_REFRESH_DELAY)
        await self.refresh_all_locked()

        while not self._stopping:
            settings = self._settings.get()
            base_interval = max(30, settings.refresh_interval_seconds)
            wait_seconds = base_interval
            if self._backoff_seconds:
                wait_seconds = min(_MAX_BACKOFF_SECONDS, self._backoff_seconds)

            if not settings.auto_refresh_enabled:
                # Still poll periodically so a settings toggle takes effect soon.
                wait_seconds = min(wait_seconds, 30)
                await asyncio.sleep(wait_seconds)
                continue

            try:
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                break
            await self.refresh_all_locked()

    async def _safe_discover(self) -> None:
        try:
            await asyncio.to_thread(self._discovery.discover_all)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Startup discovery failed: %s", exc)

    async def refresh_all_locked(self) -> None:
        if self._lock.locked():
            LOGGER.debug("Refresh already in progress; skipping overlapping trigger")
            return
        async with self._lock:
            try:
                await asyncio.to_thread(self._discovery.discover_all)
                results = await asyncio.to_thread(self._usage.refresh_all)
                self.last_refresh_ok = True
                self._backoff_seconds = 0
                LOGGER.info("Refresh-all completed for %d profile(s)", len(results))
            except Exception as exc:  # noqa: BLE001 - scheduler must never die
                self.last_refresh_ok = False
                jitter = random.uniform(0.8, 1.2)
                self._backoff_seconds = int(
                    min(_MAX_BACKOFF_SECONDS, max(30, (self._backoff_seconds or 30) * 2) * jitter)
                )
                LOGGER.warning(
                    "Refresh-all failed (%s); backing off %ds", exc, self._backoff_seconds
                )
