"""Best-effort Claude Code `/usage` command probe.

Claude Code has no stable machine-readable rate-limit endpoint. This module
runs the same slash command a user can run (`claude -p /usage`) and parses only
clear percentage/window text. If current Claude output contains no 5-hour/7-day
percentages, callers must fall back to another source.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..paths import data_dir
from ..timezones import resolve_zone
from .claude_statusline.discovery import find_claude_executable

_WINDOW_PATTERNS = {
    "five_hour": re.compile(
        r"\b(5[\s-]?h(?:our)?|five[\s-]?hour|current session)\b",
        re.IGNORECASE,
    ),
    "seven_day": re.compile(
        r"\b(7[\s-]?d(?:ay)?|seven[\s-]?day|weekly|current week)\b",
        re.IGNORECASE,
    ),
}
_PERCENT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%")
_REMAINING_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%\s*(?:remaining|left)", re.IGNORECASE)
_FULLY_USED_RE = re.compile(r"\b(fully used|exhausted|limit reached|100\s*%)\b", re.IGNORECASE)
_RESET_RE = re.compile(
    r"resets?\s+(?P<date>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{1,2}(?::\d{2})?\s*(?:am|pm))"
    r"(?:\s*\((?P<tz>[^)]+)\))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClaudeUsageCommandWindow:
    window_name: str
    used_percentage: float
    updated_utc: float
    resets_at_utc: datetime | None = None


@dataclass(frozen=True)
class ClaudeUsageCommandResult:
    ok: bool
    reason: str | None
    output: str
    windows: list[ClaudeUsageCommandWindow]
    ran_at_utc: float

    @property
    def ran_at_datetime_utc(self) -> datetime:
        return datetime.fromtimestamp(self.ran_at_utc, tz=UTC)


def _clean_output(text: str) -> str:
    ansi_re = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)")
    return ansi_re.sub("", text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _parse_reset_at(line: str, *, observed_utc: float) -> datetime | None:
    match = _RESET_RE.search(line)
    if not match:
        return None
    date_text = match.group("date").replace(" ", "")
    fmt = "%b%d,%I:%M%p" if ":" in date_text else "%b%d,%I%p"
    tz = resolve_zone(match.group("tz"))
    observed_local = datetime.fromtimestamp(observed_utc, tz=UTC).astimezone(tz.tz)
    try:
        parsed = datetime.strptime(date_text, fmt)
    except ValueError:
        return None
    local_dt = parsed.replace(year=observed_local.year, tzinfo=tz.tz)
    if local_dt < observed_local - timedelta(days=180):
        local_dt = local_dt.replace(year=local_dt.year + 1)
    elif local_dt > observed_local + timedelta(days=180):
        local_dt = local_dt.replace(year=local_dt.year - 1)
    return local_dt.astimezone(UTC)


def parse_usage_output(text: str, *, observed_utc: float | None = None) -> list[ClaudeUsageCommandWindow]:
    """Parse clear window percentages from `/usage` text.

    Current Claude Code often returns contributor diagnostics only. In that
    case this returns an empty list instead of guessing.
    """

    observed = observed_utc if observed_utc is not None else time.time()
    windows: dict[str, ClaudeUsageCommandWindow] = {}
    for raw_line in _clean_output(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        window_name = None
        for candidate, pattern in _WINDOW_PATTERNS.items():
            if pattern.search(line):
                window_name = candidate
                break
        if window_name is None:
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
        used_percent = min(100.0, max(0.0, used_percent))
        windows[window_name] = ClaudeUsageCommandWindow(
            window_name,
            used_percent,
            observed,
            _parse_reset_at(line, observed_utc=observed),
        )
    return list(windows.values())


def _probe_cwd() -> Path:
    path = data_dir() / "claude-usage-probe-workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_usage_command(profile_id: str, *, timeout_seconds: float = 12.0) -> ClaudeUsageCommandResult:
    exe = find_claude_executable()
    ran_at = time.time()
    if not exe:
        return ClaudeUsageCommandResult(False, "Claude executable not found.", "", [], ran_at)

    env = os.environ.copy()
    if profile_id:
        env["CLAUDE_CONFIG_DIR"] = profile_id

    try:
        completed = subprocess.run(
            [exe, "-p", "/usage", "--output-format", "json"],
            cwd=str(_probe_cwd()),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return ClaudeUsageCommandResult(False, "Claude `/usage` command timed out.", "", [], ran_at)
    except (OSError, subprocess.SubprocessError) as exc:
        return ClaudeUsageCommandResult(False, f"Claude `/usage` command failed: {exc}", "", [], ran_at)

    raw_output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    output = _clean_output(raw_output)
    if completed.returncode != 0:
        return ClaudeUsageCommandResult(
            False,
            f"Claude `/usage` exited with code {completed.returncode}.",
            output,
            [],
            ran_at,
        )

    usage_text = output
    try:
        payload = json.loads(output)
        result = payload.get("result")
        if isinstance(result, str):
            usage_text = result
    except json.JSONDecodeError:
        pass

    windows = parse_usage_output(usage_text, observed_utc=ran_at)
    reason = None
    if not windows:
        reason = "Claude `/usage` ran, but output did not include parseable 5-hour/7-day percentages."
    return ClaudeUsageCommandResult(True, reason, usage_text, windows, ran_at)
