"""Shared app-state dependency accessors for routers.

All services are created once in app.py's lifespan and stashed on
``request.app.state``; these helpers just type the lookups.
"""

from __future__ import annotations

from fastapi import Request

from ..db.store import Store
from ..scheduler import RefreshScheduler
from ..services.diagnostics_service import DiagnosticsService
from ..services.discovery_service import DiscoveryService
from ..services.forecast_service import ForecastService
from ..services.history_service import HistoryService
from ..services.notification_service import NotificationService
from ..services.forensics_service import ForensicsService
from ..services.settings_service import SettingsService
from ..services.usage_service import UsageService


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_discovery_service(request: Request) -> DiscoveryService:
    return request.app.state.discovery_service


def get_usage_service(request: Request) -> UsageService:
    return request.app.state.usage_service


def get_history_service(request: Request) -> HistoryService:
    return request.app.state.history_service


def get_settings_service(request: Request) -> SettingsService:
    return request.app.state.settings_service


def get_diagnostics_service(request: Request) -> DiagnosticsService:
    return request.app.state.diagnostics_service


def get_notification_service(request: Request) -> NotificationService:
    return request.app.state.notification_service


def get_forecast_service(request: Request) -> ForecastService:
    return request.app.state.forecast_service


def get_forensics_service(request: Request) -> ForensicsService:
    return request.app.state.forensics_service


def get_scheduler(request: Request) -> RefreshScheduler:
    return request.app.state.scheduler
