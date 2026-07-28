"""Discovery of Google Antigravity CLI/app data homes and projects.

Keeps the same safety shape as Codex discovery: no recursive drive scans,
only known app-data locations, explicit environment overrides, PowerShell
profile hints, and one-level home candidates.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import AntigravityProfileCandidate

LOGGER = logging.getLogger("claude_codex_monitor.vendor.antigravity.discovery")

_ENV_NAMES = ("ANTIGRAVITY_HOME", "ANTIGRAVITY_USER_DATA_DIR", "ANTIGRAVITY_CONFIG_DIR")
_ENV_RE = re.compile(
    r"\$env:(ANTIGRAVITY_HOME|ANTIGRAVITY_USER_DATA_DIR|ANTIGRAVITY_CONFIG_DIR)\s*=\s*['\"]([^'\"]+)['\"]|"
    r"(ANTIGRAVITY_HOME|ANTIGRAVITY_USER_DATA_DIR|ANTIGRAVITY_CONFIG_DIR)\s*=\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_PROFILE_FLAG_RE = re.compile(r"--profile\s+['\"]?([^'\"\s]+)['\"]?", re.I)
_USER_DATA_FLAG_RE = re.compile(r"--user-data-dir\s+['\"]?([^'\"\n]+?)['\"]?(?=\s+--|\s*$)", re.I)
_FUNC_RE = re.compile(r"function\s+([A-Za-z0-9_-]+)\s*\{(?P<body>.*?)\n\}", re.I | re.S)

_CREDIBLE_NAMES = {
    "settings.json",
    "cli.log",
    "conversation_summaries.db",
    "jetski_state.pbtxt",
    "installation_id",
    "mcp_config.json",
    "config.json",
    "User",
    "Default",
}
_CHROMIUM_PROFILE_RE = re.compile(r"^(Default|Profile \d+)$", re.I)


def find_antigravity_executable() -> Path | None:
    for name in ("agy.exe", "agy", "antigravity.exe", "antigravity"):
        hit = shutil.which(name)
        if hit:
            return Path(hit)
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"
    try:
        if local.exists():
            return local
    except OSError:
        pass
    return None


def credible_home(path: Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        return any((path / name).exists() for name in _CREDIBLE_NAMES)
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


def env_homes() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for name in _ENV_NAMES:
        if os.environ.get(name):
            out.append((Path(os.environ[name]), f"process {name}"))
    try:
        binary = shutil.which("pwsh") or shutil.which("powershell")
        if binary:
            commands = [
                f"[Environment]::GetEnvironmentVariable('{name}','User'); "
                f"[Environment]::GetEnvironmentVariable('{name}','Machine')"
                for name in _ENV_NAMES
            ]
            completed = subprocess.run(
                [binary, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", " ".join(commands)],
                text=True,
                capture_output=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            for line in [x.strip() for x in (completed.stdout or "").splitlines() if x.strip()]:
                out.append((Path(line), "user/machine Antigravity env"))
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.debug("PowerShell Antigravity env query failed: %s", exc)
    return out


def homes_from_powershell_profiles() -> list[tuple[Path, str, str | None]]:
    out: list[tuple[Path, str, str | None]] = []
    for profile in powershell_profile_paths():
        try:
            text = profile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        chunks = [(profile.name, text)]
        chunks.extend((fn.group(1), fn.group("body")) for fn in _FUNC_RE.finditer(text))
        for source_name, body in chunks:
            for match in _ENV_RE.finditer(body):
                raw = match.group(2) or match.group(4)
                out.append((expand_path(raw), f"PowerShell {source_name}", None))
            for match in _USER_DATA_FLAG_RE.finditer(body):
                out.append((expand_path(match.group(1).strip()), f"PowerShell {source_name}", None))
            for match in _PROFILE_FLAG_RE.finditer(body):
                out.append((Path.home() / ".gemini" / "antigravity-cli", f"PowerShell {source_name}", match.group(1)))
    return out


def candidate_homes() -> list[tuple[Path, str]]:
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", ""))
    localappdata = Path(os.environ.get("LOCALAPPDATA", ""))
    out: list[tuple[Path, str]] = [
        (home / ".gemini" / "antigravity-cli", "default cli home"),
        (home / ".gemini" / "antigravity", "default app home"),
    ]
    if appdata:
        out.append((appdata / "Antigravity", "roaming app data"))
    if localappdata:
        out.extend(
            [
                (localappdata / "antigravity", "local app data"),
                (localappdata / "Antigravity", "local app data"),
            ]
        )
    out.extend(env_homes())
    out.extend((path, source) for path, source, _profile in homes_from_powershell_profiles())
    try:
        gemini = home / ".gemini"
        for p in gemini.iterdir():
            if p.is_dir() and re.match(r"antigravity([_-].+)?$", p.name, re.I):
                out.append((p, "gemini home candidate"))
    except OSError as exc:
        LOGGER.debug("Cannot enumerate ~/.gemini: %s", exc)
    return out


def _project_candidates(exe: Path | None) -> list[AntigravityProfileCandidate]:
    projects = Path.home() / ".gemini" / "config" / "projects"
    out: list[AntigravityProfileCandidate] = []
    try:
        files = sorted(projects.glob("*.json"))
    except OSError:
        return out
    for project_file in files:
        try:
            data = json.loads(project_file.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        project_id = str(data.get("id") or project_file.stem)
        name = str(data.get("name") or project_id)
        out.append(
            AntigravityProfileCandidate(
                label=name,
                kind="project",
                config_home=projects,
                source=str(project_file),
                executable=exe,
                project_id=project_id,
            )
        )
    return out


def discover_profiles() -> list[AntigravityProfileCandidate]:
    exe = find_antigravity_executable()
    seen: set[tuple[str, str | None, str | None]] = set()
    profiles: list[AntigravityProfileCandidate] = []
    for home, source in candidate_homes():
        home = home.expanduser()
        if not credible_home(home):
            continue
        key = (str(home).lower(), None, None)
        if key not in seen:
            seen.add(key)
            label = "default" if home.name.lower() in {"antigravity", "antigravity-cli"} else home.name
            profiles.append(
                AntigravityProfileCandidate(
                    label=label,
                    kind="default home",
                    config_home=home,
                    source=source,
                    executable=exe,
                )
            )
        try:
            child_dirs = sorted(p for p in home.iterdir() if p.is_dir())
        except OSError as exc:
            LOGGER.debug("Cannot list Antigravity profiles under %s: %s", home, exc)
            child_dirs = []
        for child in child_dirs:
            if not _CHROMIUM_PROFILE_RE.match(child.name):
                continue
            profile_key = (str(home).lower(), None, child.name.lower())
            if profile_key in seen:
                continue
            seen.add(profile_key)
            profiles.append(
                AntigravityProfileCandidate(
                    label=f"{home.name}:{child.name}",
                    kind="user-data profile",
                    config_home=home,
                    source=str(child),
                    executable=exe,
                    profile_arg=child.name,
                )
            )
    for home, source, profile_arg in homes_from_powershell_profiles():
        if not profile_arg or not credible_home(home):
            continue
        key = (str(home).lower(), None, profile_arg.lower())
        if key in seen:
            continue
        seen.add(key)
        profiles.append(
            AntigravityProfileCandidate(
                label=f"{home.name}:{profile_arg}",
                kind="named profile",
                config_home=home,
                source=source,
                executable=exe,
                profile_arg=profile_arg,
            )
        )
    profiles.extend(_project_candidates(exe))
    return profiles
