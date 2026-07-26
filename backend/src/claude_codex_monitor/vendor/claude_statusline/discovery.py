# Adapted from I:\Projects\Automation\Claude\Notifications\claude-usage-notifier
# (not imported at runtime; copied and modified for this project).
"""Safe, repeatable discovery of Claude Code profiles.

Discovery sources, in precedence order:
  1. default        - %USERPROFILE%\\.claude
  2. env:process     - CLAUDE_CONFIG_DIR in the current process
  3. env:user        - user-level CLAUDE_CONFIG_DIR (registry)
  4. env:machine     - machine-level CLAUDE_CONFIG_DIR (registry)
  5. ps-profile      - CLAUDE_CONFIG_DIR assignments in PowerShell profiles
  6. home-candidate  - ``.claude-*`` / ``.claude_*`` dirs under the user home
  7. override        - user-maintained config entries (this app's Settings)

We never recursively scan drives: only the user home (one level) plus
explicitly named locations are examined. Simplified from the original:
dropped the standalone Config file dependency in favour of a plain list of
override dicts passed in by the caller (this app persists overrides in its
own SQLite settings table, not a separate config.json).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

LOGGER = logging.getLogger("claude_codex_monitor.vendor.claude_statusline.discovery")

SOURCE_DEFAULT = "default"
SOURCE_ENV_PROCESS = "env:process"
SOURCE_ENV_USER = "env:user"
SOURCE_ENV_MACHINE = "env:machine"
SOURCE_PS_PROFILE = "ps-profile"
SOURCE_HOME_CANDIDATE = "home-candidate"
SOURCE_OVERRIDE = "override"

_SOURCE_PRECEDENCE = {
    SOURCE_DEFAULT: 0,
    SOURCE_ENV_PROCESS: 1,
    SOURCE_ENV_USER: 2,
    SOURCE_ENV_MACHINE: 3,
    SOURCE_PS_PROFILE: 4,
    SOURCE_HOME_CANDIDATE: 5,
    SOURCE_OVERRIDE: 6,
}

_STRONG_SIGNALS = ("settings.json", ".claude.json")
_WEAK_SIGNALS = (
    "projects",
    "sessions",
    "history.jsonl",
    "shell-snapshots",
    "statsig",
    "todos",
    "file-history",
    "session-env",
    ".credentials.json",
    "plugins",
    "skills",
    "cache",
)

_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclasses.dataclass
class ClaudeProfileCandidate:
    """A discovered Claude Code profile (pre-normalisation into the app's Profile model)."""

    profile_id: str
    label: str
    config_dir: Path
    source: str
    claude_executable: str | None = None
    settings_path: Path | None = None
    launcher: str | None = None
    valid: bool = True
    reason: str = ""

    @property
    def settings_file(self) -> Path:
        return self.settings_path or (self.config_dir / "settings.json")


def safe_label(config_dir: Path, existing: set[str] | None = None) -> str:
    """Derive a filesystem/UI-safe label from a config directory name only.

    Never uses the full path, so a label can never leak a username or a
    private path into the UI, logs, or notifications.
    """
    name = config_dir.name or "claude"
    if name.startswith("."):
        name = name[1:]
    if name.startswith("claude-") or name.startswith("claude_"):
        name = name[7:]
    elif name == "claude":
        name = "default"
    label = _SAFE_LABEL_RE.sub("-", name).strip("-._")
    label = label or "claude"
    label = label[:48]
    if existing is not None:
        base = label
        counter = 2
        while label in existing:
            label = f"{base}-{counter}"
            counter += 1
        existing.add(label)
    return label


def profile_id_for(config_dir: Path) -> str:
    """Stable identifier: the normalised absolute config path, lowercased."""
    try:
        resolved = config_dir.resolve()
    except OSError:
        resolved = config_dir
    return str(resolved).rstrip("\\/").lower()


def looks_like_claude_config_dir(path: Path) -> tuple[bool, str]:
    """Return (is_credible, reason) for a candidate directory."""
    try:
        if not path.is_dir():
            return False, "not a directory"
    except OSError as exc:
        return False, f"inaccessible ({exc.__class__.__name__})"

    try:
        entries = {entry.name for entry in path.iterdir()}
    except OSError as exc:
        return False, f"unreadable ({exc.__class__.__name__})"

    strong = [name for name in _STRONG_SIGNALS if name in entries]
    weak = [name for name in _WEAK_SIGNALS if name in entries]

    if strong and (weak or len(strong) > 1):
        return True, f"config signals: {', '.join(sorted(strong + weak)[:4])}"
    if strong:
        return True, f"config signal: {strong[0]}"
    if len(weak) >= 3:
        return True, f"state signals: {', '.join(sorted(weak)[:4])}"
    if weak:
        return False, f"insufficient signals (only {', '.join(sorted(weak))})"
    return False, "no Claude configuration or state found"


_ASSIGNMENT_RE = re.compile(
    r"""\$env:CLAUDE_CONFIG_DIR
        \s*=\s*
        (?P<value>
            "(?:[^"`]|`.)*"
          | '[^']*'
          | \(?[^\s;#)]+\)?
        )""",
    re.IGNORECASE | re.VERBOSE,
)

_FUNCTION_RE = re.compile(
    r"^\s*function\s+(?P<name>[A-Za-z0-9_.\-]+)\s*(?:\{|$)", re.IGNORECASE | re.MULTILINE
)


def expand_powershell_path(value: str, home: Path | None = None) -> str | None:
    """Resolve a PowerShell string literal to a filesystem path.

    Returns None when the expression is too dynamic to resolve safely - we
    would rather skip a candidate than guess a wrong directory.
    """
    home_path = home or Path(os.path.expanduser("~"))
    text = value.strip()
    if not text:
        return None

    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    quoted_single = text.startswith("'") and text.endswith("'") and len(text) >= 2
    if (text.startswith('"') and text.endswith('"') and len(text) >= 2) or quoted_single:
        text = text[1:-1]

    if quoted_single:
        if "$" in text:
            return None
        return os.path.normpath(text) if text else None

    text = text.replace("`\"", '"')

    replacements = {
        "${env:USERPROFILE}": str(home_path),
        "$env:USERPROFILE": str(home_path),
        "${env:HOME}": str(home_path),
        "$env:HOME": str(home_path),
        "${HOME}": str(home_path),
        "$HOME": str(home_path),
        "$PSScriptRoot": "",
    }
    for token, replacement in replacements.items():
        text = text.replace(token, replacement)

    def _env_sub(match: re.Match[str]) -> str:
        return os.environ.get(match.group("name"), "\x00UNRESOLVED\x00")

    text = re.sub(r"\$\{env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}", _env_sub, text)
    text = re.sub(r"\$env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)", _env_sub, text)

    if "\x00UNRESOLVED\x00" in text or "$" in text:
        return None
    text = text.strip()
    if not text:
        return None
    return os.path.normpath(os.path.expanduser(text))


def parse_powershell_profile(text: str, home: Path | None = None) -> list[dict[str, str]]:
    """Extract CLAUDE_CONFIG_DIR assignments and their enclosing function name."""
    results: list[dict[str, str]] = []

    functions: list[tuple[int, int, str]] = []
    for match in _FUNCTION_RE.finditer(text):
        name = match.group("name")
        brace_index = text.find("{", match.end() - 1)
        if brace_index == -1:
            continue
        depth = 0
        end = len(text)
        for index in range(brace_index, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        functions.append((brace_index, end, name))

    for match in _ASSIGNMENT_RE.finditer(text):
        resolved = expand_powershell_path(match.group("value"), home=home)
        if not resolved:
            continue
        position = match.start()
        launcher = ""
        best_span = None
        for start, end, name in functions:
            if start <= position <= end:
                span = end - start
                if best_span is None or span < best_span:
                    best_span = span
                    launcher = name
        results.append(
            {
                "config_dir": resolved,
                "launcher": launcher,
                "raw": match.group("value").strip(),
            }
        )
    return results


def powershell_profile_paths() -> list[Path]:
    """Candidate PowerShell profile scripts for the current user and machine."""
    paths: list[Path] = []
    for exe in ("pwsh", "powershell"):
        binary = shutil.which(exe)
        if not binary:
            continue
        try:
            completed = subprocess.run(
                [
                    binary,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "$PROFILE.CurrentUserAllHosts; $PROFILE.CurrentUserCurrentHost; "
                    "$PROFILE.AllUsersAllHosts; $PROFILE.AllUsersCurrentHost",
                ],
                capture_output=True,
                text=True,
                timeout=25,
                encoding="utf-8",
                errors="replace",
            )
            for line in (completed.stdout or "").splitlines():
                line = line.strip()
                if line:
                    paths.append(Path(line))
        except (OSError, subprocess.SubprocessError) as exc:
            LOGGER.debug("PowerShell profile query failed for %s: %s", exe, exc)

    home = Path(os.path.expanduser("~"))
    for relative in (
        Path("Documents/PowerShell/profile.ps1"),
        Path("Documents/PowerShell/Microsoft.PowerShell_profile.ps1"),
        Path("Documents/WindowsPowerShell/profile.ps1"),
        Path("Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1"),
        Path("OneDrive/Documents/PowerShell/profile.ps1"),
        Path("OneDrive/Documents/PowerShell/Microsoft.PowerShell_profile.ps1"),
        Path("OneDrive/ドキュメント/PowerShell/profile.ps1"),
        Path("OneDrive/ドキュメント/PowerShell/Microsoft.PowerShell_profile.ps1"),
    ):
        paths.append(home / relative)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_claude_executable() -> str | None:
    """Locate the Claude Code executable without scanning the filesystem."""
    for name in ("claude.cmd", "claude.exe", "claude"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        Path(os.path.expanduser("~")) / ".local" / "bin" / "claude.exe",
        Path(os.path.expanduser("~")) / ".local" / "bin" / "claude",
        Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "npm" / "claude.cmd",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def claude_version(executable: str | None = None, timeout: float = 10.0) -> str | None:
    """Return the installed Claude Code version string, or None. Health probe only."""
    exe = executable or find_claude_executable()
    if not exe:
        return None
    try:
        completed = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (completed.stdout or completed.stderr or "").strip()
    return output.splitlines()[0].strip() if output else None


def _read_env_var(scope: str) -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    if scope == "user":
        root, subkey = winreg.HKEY_CURRENT_USER, "Environment"
    else:
        root, subkey = (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "CLAUDE_CONFIG_DIR")
            return str(value).strip() or None
    except (FileNotFoundError, OSError):
        return None


def discover_profiles(
    *,
    home: Path | None = None,
    overrides: list[dict] | None = None,
    include_invalid: bool = False,
) -> list[ClaudeProfileCandidate]:
    """Discover every usable Claude profile on this machine.

    ``overrides`` is a list of dicts: {config_dir, label?, claude_executable?,
    enabled}. This app persists overrides in its own settings store rather
    than a standalone config.json (that's the one behavioural difference from
    the vendored original).
    """
    home_path = home or Path(os.path.expanduser("~"))
    overrides = overrides or []

    candidates: dict[str, tuple[str, str, str | None]] = {}

    def add(raw_dir, source: str, launcher: str = "", label: str | None = None) -> None:
        text = str(raw_dir).strip().strip('"').strip("'")
        if not text:
            return
        try:
            path = Path(os.path.expanduser(os.path.expandvars(text)))
            key = str(path.resolve()).rstrip("\\/").lower()
        except OSError:
            key = str(text).rstrip("\\/").lower()
        existing = candidates.get(key)
        if existing is None or _SOURCE_PRECEDENCE[source] < _SOURCE_PRECEDENCE[existing[0]]:
            candidates[key] = (source, launcher or (existing[1] if existing else ""), label)
        elif launcher and not existing[1]:
            candidates[key] = (existing[0], launcher, existing[2])

    add(home_path / ".claude", SOURCE_DEFAULT)

    process_env = os.environ.get("CLAUDE_CONFIG_DIR")
    if process_env:
        add(process_env, SOURCE_ENV_PROCESS)
    for scope, source in (("user", SOURCE_ENV_USER), ("machine", SOURCE_ENV_MACHINE)):
        value = _read_env_var(scope)
        if value:
            add(value, source)

    for profile_script in powershell_profile_paths():
        try:
            if not profile_script.is_file():
                continue
            text = profile_script.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            LOGGER.debug("Cannot read PowerShell profile %s: %s", profile_script, exc)
            continue
        for entry in parse_powershell_profile(text, home=home_path):
            add(entry["config_dir"], SOURCE_PS_PROFILE, launcher=entry["launcher"])

    try:
        for entry in home_path.iterdir():
            name = entry.name.lower()
            if not entry.is_dir():
                continue
            if name.startswith(".claude-") or name.startswith(".claude_") or name == ".claude":
                add(entry, SOURCE_HOME_CANDIDATE)
    except OSError as exc:
        LOGGER.debug("Cannot enumerate home directory: %s", exc)

    for override in overrides:
        if override.get("enabled", True):
            add(override["config_dir"], SOURCE_OVERRIDE, label=override.get("label"))

    executable = find_claude_executable()
    override_exes = {}
    for o in overrides:
        exe = o.get("claude_executable")
        if exe:
            try:
                key = str(Path(os.path.expanduser(o["config_dir"])).resolve()).lower()
                override_exes[key] = exe
            except OSError:
                pass

    profiles: list[ClaudeProfileCandidate] = []
    used_labels: set[str] = set()
    for key in sorted(candidates, key=lambda k: (_SOURCE_PRECEDENCE[candidates[k][0]], k)):
        source, launcher, explicit_label = candidates[key]
        config_dir = Path(key)
        credible, reason = looks_like_claude_config_dir(config_dir)
        if not credible and source == SOURCE_OVERRIDE and config_dir.is_dir():
            credible, reason = True, "accepted via user override"
        if not credible and not include_invalid:
            LOGGER.info("Rejected candidate %s (%s)", config_dir.name, reason)
            continue

        label = explicit_label or safe_label(config_dir, used_labels)
        if explicit_label:
            used_labels.add(label)
        profiles.append(
            ClaudeProfileCandidate(
                profile_id=profile_id_for(config_dir),
                label=label,
                config_dir=config_dir,
                source=source,
                claude_executable=override_exes.get(key) or executable,
                settings_path=config_dir / "settings.json",
                launcher=launcher or None,
                valid=credible,
                reason=reason,
            )
        )
    return profiles
