# Adapted from I:\Projects\Automation\Codex\Notifications\src\ai_usage_notifier
# codex_app_server.py (not imported at runtime; copied and modified for this project).
"""Spawn `codex [--profile X] app-server --stdio` per-profile and speak the
JSON-RPC-over-stdio protocol to fetch account/rate-limit info.

Security constraints (per this project's rules):
  - Structured argument lists only, never shell=True with concatenated strings.
  - Explicit per-profile timeout.
  - Explicit minimal environment dict per profile - never mutate the global
    process environment, and never leak one profile's env into another's
    subprocess.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import CodexProfileCandidate, LimitWindow, ProbeResult

# Minimal env vars a Windows Codex subprocess needs to run at all. Nothing
# credential-shaped is added beyond what the OS itself requires to locate
# executables and temp/user dirs; CODEX_HOME is set explicitly per profile.
_BASE_ENV_VARS = (
    "PATH",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "USERNAME",
    "APPDATA",
    "LOCALAPPDATA",
    "COMSPEC",
    "PATHEXT",
    "HOMEDRIVE",
    "HOMEPATH",
)


def build_isolated_env(codex_home: Path) -> dict[str, str]:
    """Explicit minimal env for one profile's subprocess - copy only needed vars."""
    env: dict[str, str] = {}
    for var in _BASE_ENV_VARS:
        value = os.environ.get(var)
        if value is not None:
            env[var] = value
    env["CODEX_HOME"] = str(codex_home)
    return env


class AppServerClient:
    def __init__(self, profile: CodexProfileCandidate, timeout: float = 18.0):
        self.profile = profile
        self.timeout = timeout
        self.proc: subprocess.Popen | None = None
        self.next_id = 1
        self.responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self.notifications: queue.Queue[dict[str, Any]] = queue.Queue()

    def __enter__(self) -> "AppServerClient":
        exe = str(self.profile.codex_executable or "codex")
        args: list[str] = [exe]
        if self.profile.profile_arg:
            args.extend(["--profile", self.profile.profile_arg])
        args.extend(["app-server", "--stdio"])
        env = build_isolated_env(self.profile.codex_home)
        self.proc = subprocess.Popen(  # noqa: S603 - structured argv, no shell
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "claude-codex-monitor", "version": "0.1.0"},
                "capabilities": {"optOutNotificationMethods": ["thread/started"]},
            },
        )
        self.notify("initialized")
        return self

    def __exit__(self, *_exc: object) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _reader(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                self.responses.put(msg)
            else:
                self.notifications.put(msg)

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        req_id = self.next_id
        self.next_id += 1
        payload: dict[str, Any] = {"id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        while True:
            try:
                msg = self.responses.get(timeout=self.timeout)
            except queue.Empty as exc:
                if self.proc and self.proc.poll() is not None:
                    err = self.proc.stderr.read() if self.proc.stderr else ""
                    raise RuntimeError(
                        f"app-server exited with code {self.proc.returncode}: {err.strip()[:500]}"
                    ) from exc
                raise TimeoutError(f"app-server timeout waiting for {method}") from exc
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                raise RuntimeError(str(msg["error"])[:500])
            return msg.get("result")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def account(self) -> Any:
        return self.request("account/read", {"refreshToken": False})

    def rate_limits(self) -> Any:
        snap = self.request("account/rateLimits/read")
        while True:
            try:
                msg = self.notifications.get_nowait()
            except queue.Empty:
                break
            if msg.get("method") == "account/rateLimits/updated":
                params = msg.get("params") or {}
                if params.get("rateLimits"):
                    snap["rateLimits"] = _merge_sparse(snap.get("rateLimits") or {}, params["rateLimits"])
        return snap


def _merge_sparse(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_sparse(merged[key], value)
        else:
            merged[key] = value
    return merged


def safe_account_label(account_result: dict[str, Any] | None) -> tuple[str, str, str]:
    """Returns (auth_status, display_label, identity). Never includes email
    in the identity hash's public form beyond what's already shown in-label;
    callers must still treat these as sensitive-ish for logs (sanitize before
    persisting/displaying broadly)."""
    if not account_result:
        return "unknown", "unknown", "unknown"
    account = account_result.get("account")
    if not account:
        status = "unauthenticated" if account_result.get("requiresOpenaiAuth") else "not required"
        return status, status, status
    typ = account.get("type", "account")
    email = account.get("email")
    plan = account.get("planType")
    label = f"{email or typ} ({plan})" if plan else (email or typ)
    identity = f"{typ}|{email or ''}|{plan or ''}"
    return "authenticated", label, identity


def parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str) and value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        if isinstance(value, str) and "T" in value:
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        return datetime.fromtimestamp(int(value), timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def parse_rate_limits(
    profile: CodexProfileCandidate, account_label: str, account_identity: str, payload: dict[str, Any]
) -> list[LimitWindow]:
    windows: list[LimitWindow] = []
    by_id = payload.get("rateLimitsByLimitId") or {}
    if not by_id and payload.get("rateLimits"):
        snap = payload["rateLimits"]
        by_id = {snap.get("limitId") or "codex": snap}
    source_id = f"{profile.codex_home}|{account_identity}"
    for key, snap in by_id.items():
        if not isinstance(snap, dict):
            continue
        limit_id = snap.get("limitId") or str(key)
        for window_name in ("primary", "secondary"):
            win = snap.get(window_name)
            if not isinstance(win, dict):
                continue
            windows.append(
                LimitWindow(
                    source_id=source_id,
                    profile_labels=(profile.label,),
                    account_label=account_label,
                    limit_id=limit_id,
                    window_name=window_name,
                    window_duration_mins=win.get("windowDurationMins"),
                    used_percent=win.get("usedPercent"),
                    resets_at=parse_ts(win.get("resetsAt")),
                    plan_type=snap.get("planType"),
                    raw_limit_name=snap.get("limitName"),
                )
            )
    return windows


def probe_profile(profile: CodexProfileCandidate, timeout: float = 18.0) -> ProbeResult:
    """Actively spawn codex app-server for this one profile and fetch live data."""
    try:
        with AppServerClient(profile, timeout=timeout) as client:
            account = client.account()
            auth_status, account_label, identity = safe_account_label(account)
            rates = client.rate_limits()
            windows = parse_rate_limits(profile, account_label, identity, rates or {})
            return ProbeResult(
                profile=profile,
                ok=True,
                account_label=account_label,
                account_identity=identity,
                rate_limits=windows,
                raw=rates,
            )
    except Exception as exc:  # noqa: BLE001 - any subprocess/protocol failure becomes a diagnosable error
        return ProbeResult(profile=profile, ok=False, error=str(exc)[:500])
