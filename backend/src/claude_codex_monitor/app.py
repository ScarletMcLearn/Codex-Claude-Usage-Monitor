"""FastAPI application factory.

Binds 127.0.0.1 only (enforced by the launcher/uvicorn invocation, not by
this module, since TestClient needs to construct the app without binding a
socket). Lifespan wires up the DB, services and background scheduler, and
mounts the built frontend as static files so a single port serves both API
and UI.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, paths
from .adapters.fake_adapter import (
    FakeAntigravityAdapter,
    FakeClaudeAdapter,
    FakeCodexAdapter,
    FakeFreeAIAdapter,
)
from .api.routers import (
    diagnostics,
    discovery,
    forensics,
    health,
    history,
    profiles,
    providers,
    summary,
)
from .api.routers import (
    settings as settings_router,
)
from .db.store import Store
from .scheduler import RefreshScheduler
from .services.diagnostics_service import DiagnosticsService
from .services.discovery_service import DiscoveryService
from .services.forecast_service import ForecastService
from .services.forensics_service import ForensicsService
from .services.history_service import HistoryService
from .services.notification_service import NotificationService
from .services.settings_service import SettingsService
from .services.usage_service import UsageService

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _wire_services(app: FastAPI) -> None:
    paths.ensure_dirs()
    store = Store()
    if config.fake_adapters_enabled():
        discovery_service = DiscoveryService(
            store,
            claude_adapter=FakeClaudeAdapter(),
            codex_adapter=FakeCodexAdapter(),
            antigravity_adapter=FakeAntigravityAdapter(),
            free_ai_adapter=FakeFreeAIAdapter(),
        )
    else:
        discovery_service = DiscoveryService(store)
    history_service = HistoryService(store)
    settings_service = SettingsService(store)
    notification_service = NotificationService(store)
    forecast_service = ForecastService(store)
    forensics_service = ForensicsService(store)
    usage_service = UsageService(
        store, discovery_service, history_service, settings_service, notification_service
    )
    diagnostics_service = DiagnosticsService(store, discovery_service)
    scheduler = RefreshScheduler(discovery_service, usage_service, settings_service, forensics_service)

    app.state.store = store
    app.state.discovery_service = discovery_service
    app.state.history_service = history_service
    app.state.settings_service = settings_service
    app.state.notification_service = notification_service
    app.state.forecast_service = forecast_service
    app.state.forensics_service = forensics_service
    app.state.usage_service = usage_service
    app.state.diagnostics_service = diagnostics_service
    app.state.scheduler = scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wire_services(app)
    await app.state.scheduler.start()
    try:
        yield
    finally:
        await app.state.scheduler.stop()


def create_app(*, enable_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="Claude Codex Monitor",
        description="Local usage dashboard for Claude Code, Codex CLI, Antigravity, and Free-AI profiles",
        version="0.1.0",
        lifespan=lifespan if enable_lifespan else None,
    )

    if not enable_lifespan:
        # Test convenience: wire services synchronously without the scheduler loop.
        _wire_services(app)

    app.include_router(health.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")
    app.include_router(profiles.router, prefix="/api")
    app.include_router(discovery.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(forensics.router, prefix="/api")
    app.include_router(summary.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(diagnostics.router, prefix="/api")

    if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
