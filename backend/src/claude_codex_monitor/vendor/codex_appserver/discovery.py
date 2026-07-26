# Adapted from I:\Projects\Automation\Codex\Notifications\src\ai_usage_notifier
# (not imported at runtime; copied and modified for this project).
"""Discovery of Codex CLI homes and named sub-profiles.

Never recursively scans drives: only the user home (one level) plus
explicitly named PowerShell-profile / override locations.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import CodexProfileCandidate

LOGGER = logging.getLogger("claude_codex_monitor.vendor.codex_appserver.discovery")

_CODEX_HOME_RE = re.compile(
    r"\$env:CODEX_HOME\s*=\s*['\"]([^'\"]+)['\"]|CODEX_HOME\s*=\s*['\"]([^'\"]+)['\"]", re.I
)
_FUNC_RE = re.compile(r"function\s+([A-Za-z0-9_-]+)\s*\{(?P<body>.*?)\n\}", re.I | re.S)

_CREDIBLE_NAMES = {"config.toml", "auth.json", "state_5.sqlite", "session_index.jsonl", "version.json"}


def find_codex_executable() -> Path | None:
    hit = shutil.which("codex.exe") or shutil.which("codex")
    return Path(hit) if hit else None


def credible_home(path: Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        if any((path / n).exists() for n in _CREDIBLE_NAMES):
            return True
        return any(path.glob("*.config.toml"))
    except OSError:
        return False


def expand_path(raw: str) -> Path:
    text = raw.replace("$HOME", str(Path.home())).replace("~", str(Path.home()))
    text = os.path.expandvars(text)
    return Path(text)


def powershell_profile_paths() -> list[Path]:
    home = Path.home()
    docs_jp = home / "OneDrive" / "ドキュメント" / "PowerShell"
    candidates = [
        home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
        home / "Documents" / "PowerShell" / "profile.ps1",
        docs_jp / "Microsoft.PowerShell_profile.ps1",
        docs_jp / "profile.ps1",
    ]
    out = []
    for p in candidates:
        try:
            if p.exists():
                out.append(p)
        except OSError:
            pass
    return out


def homes_from_powershell_profiles() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for profile in powershell_profile_paths():
        try:
            text = profile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _CODEX_HOME_RE.finditer(text):
            raw = match.group(1) or match.group(2)
            out.append((expand_path(raw), f"PowerShell profile {profile.name}"))
        for fn in _FUNC_RE.finditer(text):
            body = fn.group("body")
            for match in _CODEX_HOME_RE.finditer(body):
                raw = match.group(1) or match.group(2)
                out.append((expand_path(raw), f"PowerShell function {fn.group(1)}"))
    return out


def env_codex_homes() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if os.environ.get("CODEX_HOME"):
        out.append((Path(os.environ["CODEX_HOME"]), "process CODEX_HOME"))
    try:
        binary = shutil.which("pwsh") or shutil.which("powershell")
        if binary:
            script = (
                "Get-ChildItem Env:CODEX_HOME -ErrorAction SilentlyContinue | % Value; "
                "[Environment]::GetEnvironmentVariable('CODEX_HOME','User'); "
                "[Environment]::GetEnvironmentVariable('CODEX_HOME','Machine')"
            )
            completed = subprocess.run(
                [binary, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                text=True,
                capture_output=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            lines = [x.strip() for x in (completed.stdout or "").splitlines() if x.strip()]
            labels = ["process/user/machine CODEX_HOME", "user CODEX_HOME", "machine CODEX_HOME"]
            for i, line in enumerate(lines):
                out.append((Path(line), labels[min(i, 2)]))
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.debug("PowerShell CODEX_HOME query failed: %s", exc)
    return out


def candidate_homes() -> list[tuple[Path, str]]:
    home = Path.home()
    out: list[tuple[Path, str]] = [(home / ".codex", "default home")]
    out.extend(env_codex_homes())
    out.extend(homes_from_powershell_profiles())
    try:
        for p in home.iterdir():
            if p.is_dir() and re.match(r"\.codex([_-].+)?$", p.name, re.I):
                out.append((p, "home candidate"))
    except OSError as exc:
        LOGGER.debug("Cannot enumerate home directory: %s", exc)
    return out


def discover_profiles(overrides: list[dict] | None = None) -> list[CodexProfileCandidate]:
    """Discover Codex homes and named sub-profiles (``-p/--profile <name>``
    layered ``$CODEX_HOME/<name>.config.toml`` files).
    """
    exe = find_codex_executable()
    seen_homes: set[str] = set()
    profiles: list[CodexProfileCandidate] = []
    for home, source in candidate_homes():
        home = home.expanduser()
        key = str(home).lower()
        if key in seen_homes or not credible_home(home):
            continue
        seen_homes.add(key)
        kind = "default home" if home == Path.home() / ".codex" else "isolated home"
        label = "default" if kind == "default home" else home.name
        profiles.append(
            CodexProfileCandidate(
                label=label, kind=kind, codex_home=home, codex_executable=exe, source=source
            )
        )
        try:
            for config_file in sorted(home.glob("*.config.toml")):
                name = config_file.name
                if name.endswith(".config.toml"):
                    name = name[: -len(".config.toml")]
                profiles.append(
                    CodexProfileCandidate(
                        label=f"{label}:{name}",
                        kind="named config profile",
                        codex_home=home,
                        codex_executable=exe,
                        profile_arg=name,
                        source=str(config_file),
                    )
                )
        except OSError as exc:
            LOGGER.debug("Cannot list config profiles under %s: %s", home, exc)

    for item in overrides or []:
        home = Path(item.get("codex_home", "")).expanduser()
        if credible_home(home):
            profiles.append(
                CodexProfileCandidate(
                    label=item.get("label") or home.name,
                    kind=item.get("kind") or "isolated home",
                    codex_home=home,
                    codex_executable=exe,
                    profile_arg=item.get("profile_arg"),
                    source="config override",
                )
            )
    return profiles
