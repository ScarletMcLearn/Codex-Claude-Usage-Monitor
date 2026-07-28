"""Best-effort Antigravity CLI `/usage` command probe."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ...paths import data_dir
from .discovery import find_antigravity_executable
from .models import AntigravityProfileCandidate

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
_PERCENT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_REMAINING_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%\s*(?:remaining|left|available)", re.I)
_FULLY_USED_RE = re.compile(r"\b(fully used|exhausted|limit reached|100\s*%)\b", re.I)
_LABEL_SPLIT_RE = re.compile(r"\s{2,}|[:|]|\s+-\s+")
_TOKEN_USAGE_KEYS = {"input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens", "total_tokens"}
_SNAPSHOT_ENV = "CCM_ANTIGRAVITY_USAGE_SNAPSHOT"


@dataclass(frozen=True)
class AntigravityUsageCommandWindow:
    window_name: str
    window_label: str
    used_percentage: float
    updated_utc: float


@dataclass(frozen=True)
class AntigravityUsageCommandResult:
    ok: bool
    reason: str | None
    output: str
    windows: list[AntigravityUsageCommandWindow]
    ran_at_utc: float

    @property
    def ran_at_datetime_utc(self) -> datetime:
        return datetime.fromtimestamp(self.ran_at_utc, tz=UTC)


def _clean_output(text: str) -> str:
    return _ANSI_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return value[:80] or "usage"


def _label_for_line(line: str) -> str:
    before_percent = line[: _PERCENT_RE.search(line).start()] if _PERCENT_RE.search(line) else line
    parts = [part.strip(" -\t") for part in _LABEL_SPLIT_RE.split(before_percent) if part.strip(" -\t")]
    label = parts[-1] if parts else before_percent.strip(" -\t")
    return label[:80] or "Usage"


def parse_usage_output(
    text: str, *, observed_utc: float | None = None
) -> list[AntigravityUsageCommandWindow]:
    """Parse explicit quota percentages from Antigravity `/usage` text.

    Antigravity's JSON envelope also has command token accounting under
    `usage`; callers must pass only human quota text here.
    """

    observed = observed_utc if observed_utc is not None else time.time()
    windows: dict[str, AntigravityUsageCommandWindow] = {}
    current_group: str | None = None
    pending_limit: str | None = None
    lines = _clean_output(text).splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        line = line.lstrip("│└├─ ").strip()

        if line.isupper() and "MODELS" in line:
            current_group = line.title()
            pending_limit = None
            continue

        if "limit" in line.lower() and "%" not in line:
            pending_limit = line
            continue

        if "%" not in line:
            continue

        used_percent: float | None = None
        if _FULLY_USED_RE.search(line):
            used_percent = 100.0
        else:
            remaining = _REMAINING_RE.search(line)
            if remaining:
                used_percent = 100.0 - float(remaining.group("value"))
            else:
                percent = _PERCENT_RE.search(line)
                if percent:
                    used_percent = float(percent.group("value"))

        if used_percent is None:
            continue
        next_line = ""
        for following in lines[index + 1 :]:
            next_line = following.strip().lstrip("│└├─ ").strip()
            if next_line:
                break
        if "quota available" in next_line.lower():
            used_percent = 100.0 - used_percent
        used_percent = min(100.0, max(0.0, used_percent))
        if pending_limit:
            label = f"{current_group}: {pending_limit}" if current_group else pending_limit
            pending_limit = None
        else:
            label = _label_for_line(line)
        key = _slug(label)
        windows[key] = AntigravityUsageCommandWindow(key, label, used_percent, observed)
    return list(windows.values())


def _probe_cwd() -> Path:
    path = data_dir() / "antigravity-usage-probe-workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def usage_snapshot_path() -> Path:
    configured = os.environ.get(_SNAPSHOT_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".gemini" / "antigravity-cli" / "usage.txt"


def read_usage_snapshot() -> AntigravityUsageCommandResult | None:
    path = usage_snapshot_path()
    try:
        if not path.exists() or not path.is_file():
            return None
        stat = path.stat()
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return AntigravityUsageCommandResult(
            False,
            f"Antigravity usage snapshot could not be read: {exc}",
            "",
            [],
            time.time(),
        )

    observed = stat.st_mtime
    windows = parse_usage_output(text, observed_utc=observed)
    reason = None
    if not windows:
        reason = "Antigravity usage snapshot did not include parseable quota percentages."
    return AntigravityUsageCommandResult(True, reason, text, windows, observed)


def _extract_response_text(output: str) -> str:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return output
    response = payload.get("response")
    if isinstance(response, str) and response.strip():
        return response
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error
    # Ignore payload["usage"]: those are command tokens, not model quota.
    if isinstance(payload.get("usage"), dict) and set(payload["usage"]).issuperset(_TOKEN_USAGE_KEYS):
        return ""
    return output


def _looks_like_usage_help(text: str) -> bool:
    lowered = text.lower()
    return (
        "/usage" in lowered
        and ("type" in lowered or "typing" in lowered)
        and ("directly" in lowered or "inside the cli" in lowered or "cli interface" in lowered)
    )


def run_usage_command(
    profile: AntigravityProfileCandidate, *, timeout_seconds: float = 30.0
) -> AntigravityUsageCommandResult:
    exe = profile.executable or find_antigravity_executable()
    ran_at = time.time()
    if not exe:
        return AntigravityUsageCommandResult(False, "agy executable not found.", "", [], ran_at)

    args = [
        str(exe),
        "-p",
        "/usage",
        "--output-format",
        "json",
        "--print-timeout",
        f"{int(timeout_seconds)}s",
    ]
    if profile.project_id:
        args.extend(["--project", profile.project_id])

    log_file = _probe_cwd() / "agy-usage-probe.log"
    args.extend(["--log-file", str(log_file)])

    try:
        completed = subprocess.run(
            args,
            cwd=str(_probe_cwd()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 5,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return AntigravityUsageCommandResult(False, "Antigravity `/usage` command timed out.", "", [], ran_at)
    except (OSError, subprocess.SubprocessError) as exc:
        return AntigravityUsageCommandResult(False, f"Antigravity `/usage` command failed: {exc}", "", [], ran_at)

    output = _clean_output((completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else ""))
    usage_text = _extract_response_text(output)
    if completed.returncode != 0:
        reason = f"Antigravity `/usage` exited with code {completed.returncode}."
        if usage_text:
            reason = f"{reason} {usage_text[:240]}"
        return AntigravityUsageCommandResult(False, reason[:300], usage_text, [], ran_at)

    windows = parse_usage_output(usage_text, observed_utc=ran_at)
    reason = None
    if not windows:
        if _looks_like_usage_help(usage_text):
            reason = (
                "Antigravity print mode treated `/usage` as a normal prompt, not as the "
                "interactive slash-command usage panel."
            )
        else:
            reason = "Antigravity `/usage` ran, but output did not include parseable quota percentages."
    return AntigravityUsageCommandResult(True, reason, usage_text, windows, ran_at)
