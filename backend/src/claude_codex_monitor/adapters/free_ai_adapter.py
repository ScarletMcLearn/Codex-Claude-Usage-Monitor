"""Free-AI passive provider adapter.

This adapter is intentionally zero-token: it never starts Free-AI, runs
doctor/tests, opens the router, or calls model/provider APIs. It reads only
local config/env/log files from the Free-AI repo.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..models.diagnostics import ProfileDiagnostics
from ..models.profile import ProfileStatus, sanitize_path
from ..models.usage import DataQuality, UsageLimit

DEFAULT_FREE_AI_REPO = Path(r"H:\Projects\AI\Free-AI\Free-AI")
_LOG_PATTERN = "free-ai-*.log"
_ATTEMPT_RE = re.compile(r"\brouter\s+(.+)$")


@dataclass(frozen=True)
class FreeAIProviderRoute:
    id: str
    label: str
    model: str
    credential_envs: tuple[str, ...]
    configured: bool
    quota_pool: str | None = None


@dataclass(frozen=True)
class FreeAIUsageSample:
    provider_id: str
    model: str
    count: int
    latest_log_mtime_utc: datetime


def free_ai_repo_path() -> Path:
    raw = os.environ.get("CCM_FREE_AI_REPO")
    return Path(raw) if raw else DEFAULT_FREE_AI_REPO


def credible_repo(repo: Path) -> bool:
    return (
        repo.exists()
        and (repo / "package.json").is_file()
        and (repo / "config" / "free-providers.json").is_file()
        and (repo / ".env.example").is_file()
    )


def read_dotenv_flags(path: Path) -> dict[str, bool]:
    values: dict[str, bool] = {}
    if not path.is_file():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
            continue
        key, value = trimmed.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = bool(value)
    return values


def read_routes(repo: Path) -> list[FreeAIProviderRoute]:
    config_path = repo / "config" / "free-providers.json"
    env_flags = read_dotenv_flags(repo / ".env")
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    routes: list[FreeAIProviderRoute] = []
    for item in cfg.get("route", []):
        if item.get("free") is not True or item.get("costUsd") != 0:
            continue
        credential_envs = item.get("credentialEnvs")
        if not isinstance(credential_envs, list):
            credential_env = item.get("credentialEnv")
            credential_envs = [credential_env] if credential_env else []
        env_names = tuple(str(name) for name in credential_envs if name)
        routes.append(
            FreeAIProviderRoute(
                id=str(item.get("id") or "unknown"),
                label=str(item.get("label") or item.get("id") or "Unknown"),
                model=str(item.get("model") or "unknown"),
                credential_envs=env_names,
                configured=all(env_flags.get(name, False) for name in env_names),
                quota_pool=str(item.get("quotaPool")) if item.get("quotaPool") else None,
            )
        )
    return routes


def parse_attempt_line(line: str) -> dict[str, str] | None:
    match = _ATTEMPT_RE.search(line)
    if not match:
        return None
    fields: dict[str, str] = {}
    for part in match.group(1).split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value
    if fields.get("result") != "success":
        return None
    provider = fields.get("provider")
    model = fields.get("model")
    if not provider or not model:
        return None
    return {"provider": provider, "model": model}


def read_usage_samples(repo: Path) -> list[FreeAIUsageSample]:
    log_dir = repo / "artifacts" / "logs"
    if not log_dir.is_dir():
        return []

    counts: Counter[tuple[str, str]] = Counter()
    latest_mtime: float | None = None
    for log_path in sorted(log_dir.glob(_LOG_PATTERN)):
        if not log_path.is_file():
            continue
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            mtime = log_path.stat().st_mtime
        except OSError:
            continue
        latest_mtime = max(latest_mtime or mtime, mtime)
        for line in text.splitlines():
            parsed = parse_attempt_line(line)
            if parsed:
                counts[(parsed["provider"], parsed["model"])] += 1

    if not counts or latest_mtime is None:
        return []
    observed = datetime.fromtimestamp(latest_mtime, tz=UTC)
    return [
        FreeAIUsageSample(provider_id=provider, model=model, count=count, latest_log_mtime_utc=observed)
        for (provider, model), count in sorted(counts.items())
    ]


class FreeAIProviderAdapter:
    provider_name = "free_ai"

    def __init__(self, repo: Path | None = None) -> None:
        self._repo = repo

    @property
    def repo(self) -> Path:
        return self._repo or free_ai_repo_path()

    def discover_profiles(self) -> list[ProfileStatus]:
        repo = self.repo
        if not credible_repo(repo):
            return []
        return [
            ProfileStatus(
                provider=self.provider_name,
                profile_id=str(repo.resolve()).lower(),
                profile_key=f"{self.provider_name}:{str(repo.resolve()).lower()}",
                label="Free-AI",
                sanitized_source=sanitize_path(str(repo)),
                discovery_source="CCM_FREE_AI_REPO" if os.environ.get("CCM_FREE_AI_REPO") else "default repo",
                is_active=True,
                executable_found=True,
            )
        ]

    def validate_profile(self, profile: ProfileStatus) -> tuple[bool, str]:
        if credible_repo(self.repo):
            return True, "credible Free-AI repo"
        return False, "Free-AI repo missing required files"

    def fetch_usage(self, profile: ProfileStatus) -> dict[str, Any]:
        repo = self.repo
        if not credible_repo(repo):
            return {"ok": False, "error": "Free-AI repo missing required files.", "repo": repo}
        routes = read_routes(repo)
        samples = read_usage_samples(repo)
        if not samples:
            return {
                "ok": False,
                "error": "No Free-AI router usage logs found yet.",
                "repo": repo,
                "routes": routes,
                "samples": samples,
            }
        return {"ok": True, "repo": repo, "routes": routes, "samples": samples}

    def parse_usage(self, profile: ProfileStatus, raw: dict[str, Any]) -> list[UsageLimit]:
        now = datetime.now(UTC)
        routes: list[FreeAIProviderRoute] = raw.get("routes") or []
        configured = [route for route in routes if route.configured]
        configured_ids = [route.id for route in configured]
        configured_models = [{"provider": route.id, "model": route.model} for route in configured]

        if not raw.get("ok"):
            return [
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id="unknown",
                    window_label="Local router usage",
                    quality=DataQuality.UNAVAILABLE,
                    unavailable_reason=str(raw.get("error") or "Free-AI usage unavailable.")[:300],
                    observed_at_utc=now,
                    source_detail={
                        "source": "free_ai_local_files",
                        "repo": sanitize_path(str(raw.get("repo") or self.repo)),
                        "configured_provider_ids": configured_ids,
                        "configured_provider_count": len(configured),
                        "configured_models": configured_models,
                        "secret_values_exposed": False,
                    },
                )
            ]

        labels = {route.id: route.label for route in routes}
        credential_envs = {route.id: list(route.credential_envs) for route in routes}
        route_configured = {route.id: route.configured for route in routes}
        results: list[UsageLimit] = []
        for sample in raw.get("samples") or []:
            window_id = _window_id(sample.provider_id, sample.model)
            results.append(
                UsageLimit(
                    provider=self.provider_name,
                    profile_id=profile.profile_id,
                    window_id=window_id,
                    window_label=f"{labels.get(sample.provider_id, sample.provider_id)} / {sample.model}",
                    used_units=float(sample.count),
                    max_units=None,
                    used_percent=None,
                    remaining_percent=None,
                    reset_confirmed=False,
                    quality=DataQuality.VERIFIED,
                    observed_at_utc=sample.latest_log_mtime_utc,
                    source_detail={
                        "source": "free_ai_local_router_logs",
                        "repo": sanitize_path(str(raw.get("repo") or self.repo)),
                        "provider_id": sample.provider_id,
                        "model": sample.model,
                        "successful_request_count": sample.count,
                        "configured": route_configured.get(sample.provider_id),
                        "required_env_names": credential_envs.get(sample.provider_id, []),
                        "secret_values_exposed": False,
                    },
                )
            )
        return results

    def get_account_metadata(self, profile: ProfileStatus) -> dict[str, Any]:
        routes = read_routes(self.repo) if credible_repo(self.repo) else []
        return {
            "configured_provider_count": sum(1 for route in routes if route.configured),
            "provider_count": len(routes),
        }

    def diagnose_error(self, profile: ProfileStatus, error: Exception | str) -> ProfileDiagnostics:
        valid, reason = self.validate_profile(profile)
        return ProfileDiagnostics(
            provider=self.provider_name,
            profile_id=profile.profile_id,
            profile_key=profile.profile_key,
            discovery_source=profile.discovery_source,
            sanitized_config_path=profile.sanitized_source,
            last_command_result=(
                "Free-AI local files/logs are readable." if valid else "Free-AI repo is not discoverable."
            ),
            parser_used="free_ai_local_files",
            current_error=str(error)[:300] if error else None,
            suggested_action=(
                "Run Free-AI normally to create router logs; the monitor will read local logs only."
                if valid
                else reason
            ),
        )


def _window_id(provider_id: str, model: str) -> str:
    raw = f"{provider_id}_{model}".lower()
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_") or "free_ai_usage"
