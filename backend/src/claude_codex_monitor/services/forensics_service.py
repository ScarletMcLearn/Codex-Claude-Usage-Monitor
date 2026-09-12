"""Passive forensic telemetry ingestion and export.

This module never calls model APIs, never starts AI agents, and never runs
provider CLI commands. It reads local files only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import paths
from ..db.store import Store
from ..models.profile import sanitize_path
from ..adapters.free_ai_adapter import free_ai_repo_path, read_usage_samples, credible_repo
from ..vendor.antigravity.usage_command import read_usage_snapshot, usage_snapshot_path

PARSER_VERSION = "forensics.v1"
_TEXT_KEYS = ("content", "text", "message", "prompt", "output", "response")


class ForensicsService:
    def __init__(self, store: Store) -> None:
        self._store = store

    def refresh(self) -> dict[str, Any]:
        started = datetime.now(UTC)
        result = {
            "started_at_utc": started.isoformat(),
            "sources_scanned": 0,
            "events_processed": 0,
            "events_skipped": 0,
            "malformed_events": 0,
            "model_generation_requests": 0,
        }
        for source in self._discover_sources():
            stats = self._ingest_jsonl_source(source)
            result["sources_scanned"] += 1
            result["events_processed"] += stats["events_processed"]
            result["events_skipped"] += stats["events_skipped"]
            result["malformed_events"] += stats["malformed_events"]
        result["events_processed"] += self._ingest_free_ai_summary()
        result["events_processed"] += self._ingest_antigravity_snapshot()
        result["finished_at_utc"] = datetime.now(UTC).isoformat()
        return result

    def overview(self) -> dict[str, Any]:
        return self._store.forensic_overview()

    def sessions(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self._store.list_forensic_sessions(limit=limit, offset=offset)

    def session_detail(self, session_id: str) -> dict[str, Any] | None:
        return self._store.forensic_session_detail(session_id)

    def export(self, *, export_type: str, warning_ack: bool) -> dict[str, Any]:
        if export_type == "full" and not warning_ack:
            raise ValueError("Full forensic export may contain prompts, source code, command output, and model output. Set warning_ack=true.")
        export_dir = paths.data_dir() / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = export_dir / f"token-forensics-{export_type}-{stamp}.zip"
        tables = ["agents", "sessions", "turns"]
        if export_type == "full":
            tables += ["messages", "tools", "commands", "context-blocks", "raw-events"]
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "created_at_utc": datetime.now(UTC).isoformat(),
                "export_type": export_type,
                "zero_ai_tokens": True,
                "warning": "Full exports can contain sensitive local prompts, responses, code, and command output.",
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zf.writestr("summary.json", json.dumps(self.overview(), indent=2))
            for table in tables:
                lines = "\n".join(json.dumps(row, ensure_ascii=False) for row in self._store.list_forensic_table(table))
                zf.writestr(f"{table}.jsonl", lines + ("\n" if lines else ""))
            zf.writestr("report.md", _report_markdown(self.overview()))
        return {"path": str(out), "export_type": export_type, "created_at_utc": datetime.now(UTC).isoformat()}

    def _discover_sources(self) -> list[dict[str, Any]]:
        candidates: list[tuple[str, Path, str]] = []
        codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
        for root, agent in ((codex_home, "codex"), (claude_home, "claude")):
            for sub in ("sessions", "projects", "history"):
                base = root / sub
                if base.is_dir():
                    candidates.extend((agent, p, "jsonl") for p in base.rglob("*.jsonl") if p.is_file())
        sources = []
        for agent, path, source_type in candidates:
            try:
                stat = path.stat()
            except OSError:
                continue
            sources.append(
                {
                    "source_id": _stable_id(agent, str(path)),
                    "agent": agent,
                    "source_type": source_type,
                    "source_path": str(path),
                    "parser_version": PARSER_VERSION,
                    "file_size": stat.st_size,
                    "file_mtime_utc": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                }
            )
        return sources

    def _ingest_jsonl_source(self, source: dict[str, Any]) -> dict[str, int]:
        self._store.upsert_forensic_source(source)
        current = self._store.get_forensic_source(source["source_id"]) or {}
        checkpoint = int(current.get("checkpoint_offset") or 0)
        path = Path(source["source_path"])
        try:
            size = path.stat().st_size
        except OSError as exc:
            self._store.update_forensic_source_checkpoint(
                source["source_id"], checkpoint_offset=checkpoint, events_processed=0,
                events_skipped=0, malformed_events=0, last_error=str(exc)[:300],
            )
            return {"events_processed": 0, "events_skipped": 0, "malformed_events": 0}
        if size < checkpoint:
            checkpoint = 0

        sessions: dict[str, dict[str, Any]] = {}
        turns: list[dict[str, Any]] = []
        messages: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        commands: list[dict[str, Any]] = []
        contexts: list[dict[str, Any]] = []
        raw_events: list[dict[str, Any]] = []
        processed = skipped = malformed = 0
        offset = checkpoint
        with path.open("rb") as fh:
            fh.seek(checkpoint)
            for line in fh:
                line_offset = offset
                offset += len(line)
                stripped = line.strip()
                if not stripped:
                    skipped += 1
                    continue
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if not isinstance(raw, dict):
                    skipped += 1
                    continue
                event = _normalize_event(source, raw, line_offset, processed)
                raw_events.append(event["raw_event"])
                sessions[event["session"]["session_id"]] = _merge_session(
                    sessions.get(event["session"]["session_id"]), event["session"]
                )
                if event.get("turn"):
                    turns.append(event["turn"])
                messages.extend(event["messages"])
                tools.extend(event["tools"])
                commands.extend(event["commands"])
                contexts.extend(event["contexts"])
                processed += 1
        self._store.insert_forensic_rows(
            sessions=list(sessions.values()), turns=turns, messages=messages,
            tools=tools, commands=commands, contexts=contexts, raw_events=raw_events,
        )
        self._store.update_forensic_source_checkpoint(
            source["source_id"], checkpoint_offset=offset, events_processed=processed,
            events_skipped=skipped, malformed_events=malformed,
        )
        return {"events_processed": processed, "events_skipped": skipped, "malformed_events": malformed}

    def _ingest_free_ai_summary(self) -> int:
        repo = free_ai_repo_path()
        if not credible_repo(repo):
            return 0
        source_id = _stable_id("free_ai", str(repo / "artifacts" / "logs"))
        now = datetime.now(UTC).isoformat()
        self._store.upsert_forensic_source({
            "source_id": source_id, "agent": "free_ai", "source_type": "router_logs",
            "source_path": sanitize_path(str(repo / "artifacts" / "logs")),
            "parser_version": PARSER_VERSION,
        })
        sessions = []
        for sample in read_usage_samples(repo):
            sid = _stable_id("free_ai", sample.provider_id, sample.model)
            sessions.append({
                "session_id": sid, "agent": "free_ai", "provider": sample.provider_id,
                "model": sample.model, "project_path": sanitize_path(str(repo)),
                "started_at_utc": sample.latest_log_mtime_utc.isoformat(),
                "ended_at_utc": sample.latest_log_mtime_utc.isoformat(),
                "source_id": source_id, "raw_event_count": sample.count,
                "token_quality": "unknown",
            })
        if sessions:
            self._store.insert_forensic_rows(
                sessions=sessions, turns=[], messages=[], tools=[], commands=[], contexts=[], raw_events=[]
            )
            self._store.update_forensic_source_checkpoint(
                source_id, checkpoint_offset=0, events_processed=len(sessions),
                events_skipped=0, malformed_events=0,
            )
        return len(sessions)

    def _ingest_antigravity_snapshot(self) -> int:
        snapshot = read_usage_snapshot()
        if snapshot is None:
            return 0
        source_path = usage_snapshot_path()
        source_id = _stable_id("antigravity", str(source_path))
        self._store.upsert_forensic_source({
            "source_id": source_id, "agent": "antigravity", "source_type": "usage_snapshot",
            "source_path": sanitize_path(str(source_path)), "parser_version": PARSER_VERSION,
        })
        session_id = _stable_id("antigravity", "usage_snapshot")
        sessions = [{
            "session_id": session_id, "agent": "antigravity", "provider": "google",
            "started_at_utc": datetime.now(UTC).isoformat(), "ended_at_utc": datetime.now(UTC).isoformat(),
            "source_id": source_id, "raw_event_count": len(snapshot.windows), "token_quality": "unknown",
        }]
        self._store.insert_forensic_rows(
            sessions=sessions, turns=[], messages=[], tools=[], commands=[], contexts=[], raw_events=[]
        )
        return 1


def _normalize_event(source: dict[str, Any], raw: dict[str, Any], offset: int, index: int) -> dict[str, Any]:
    raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    raw_hash = _sha(raw_json)
    raw_event_id = _stable_id(source["source_id"], str(offset), raw_hash)
    ts = _first_str(raw, ("timestamp", "created_at", "createdAt", "time", "ts"))
    timestamp = _normalize_ts(ts)
    session_id = str(
        _nested(raw, ("session_id", "sessionId", "conversation_id", "conversationId", "thread_id", "threadId", "id"))
        or _stable_id(source["agent"], source["source_path"])
    )
    event_type = str(_nested(raw, ("type", "event", "event_type", "kind", "msg_type")) or "event")
    model = _find_key(raw, {"model", "model_name", "modelName"})
    cwd = _find_key(raw, {"cwd", "working_directory", "workingDirectory"})
    usage = _find_usage(raw)
    role = str(_find_key(raw, {"role"}) or "")
    texts = _extract_texts(raw)
    user_text = next((t for r, t in texts if r == "user"), None)
    assistant_text = next((t for r, t in texts if r == "assistant"), None)
    turn_id = _stable_id(session_id, str(index), raw_event_id)
    turn = {
        "turn_id": turn_id,
        "session_id": session_id,
        "turn_index": index,
        "request_id": str(_find_key(raw, {"request_id", "requestId"}) or "") or None,
        "response_id": str(_find_key(raw, {"response_id", "responseId"}) or "") or None,
        "role": role or None,
        "event_type": event_type,
        "timestamp_utc": timestamp,
        "model": model,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cached_tokens": usage.get("cached_tokens"),
        "cache_write_tokens": usage.get("cache_write_tokens"),
        "reasoning_tokens": usage.get("reasoning_tokens"),
        "context_tokens": usage.get("context_tokens"),
        "duration_ms": _int_or_none(_find_key(raw, {"duration_ms", "durationMs", "elapsed_ms"})),
        "token_quality": "reported" if any(v is not None for v in usage.values()) else "unknown",
        "provenance_json": json.dumps({"source_id": source["source_id"], "offset": offset, "parser_version": PARSER_VERSION}),
        "user_preview": _preview(user_text),
        "assistant_preview": _preview(assistant_text),
        "content_hash": raw_hash,
        "raw_event_id": raw_event_id,
    }
    messages = []
    contexts = []
    for pos, (msg_role, text) in enumerate(texts):
        stats = _text_stats(text)
        msg_id = _stable_id(raw_event_id, "message", str(pos), msg_role, stats["hash"])
        messages.append({
            "message_id": msg_id, "session_id": session_id, "turn_id": turn_id,
            "role": msg_role, "timestamp_utc": timestamp, "text": text,
            "char_count": stats["chars"], "byte_count": stats["bytes"],
            "line_count": stats["lines"], "content_hash": stats["hash"],
            "estimated_tokens": _estimate_tokens(text), "token_quality": "estimated",
            "source_id": source["source_id"], "raw_event_id": raw_event_id,
        })
        contexts.append({
            "block_id": _stable_id(raw_event_id, "context", str(pos), stats["hash"]),
            "session_id": session_id, "turn_id": turn_id,
            "category": _context_category(msg_role), "source": event_type, "text": text,
            "char_count": stats["chars"], "byte_count": stats["bytes"],
            "line_count": stats["lines"], "content_hash": stats["hash"],
            "estimated_tokens": _estimate_tokens(text), "token_quality": "estimated",
            "first_seen_utc": timestamp, "raw_event_id": raw_event_id,
        })
    tools = _extract_tools(raw, session_id, turn_id, raw_event_id)
    commands = _extract_commands(raw, session_id, turn_id, raw_event_id)
    session = {
        "session_id": session_id, "agent": source["agent"], "provider": _provider_for(source["agent"]),
        "model": model, "project_path": sanitize_path(str(cwd)) if cwd else None,
        "started_at_utc": timestamp, "ended_at_utc": timestamp, "source_id": source["source_id"],
        "raw_event_count": 1, **usage, "token_quality": turn["token_quality"],
    }
    return {
        "session": session,
        "turn": turn,
        "messages": messages,
        "tools": tools,
        "commands": commands,
        "contexts": contexts,
        "raw_event": {
            "raw_event_id": raw_event_id, "source_id": source["source_id"],
            "session_id": session_id, "event_index": index, "byte_offset": offset,
            "timestamp_utc": timestamp, "event_type": event_type,
            "content_hash": raw_hash, "raw_json": raw_json,
        },
    }


def _find_usage(raw: dict[str, Any]) -> dict[str, int | None]:
    usage_obj = raw.get("usage") if isinstance(raw.get("usage"), dict) else raw
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens", "inputTokens"),
        "output_tokens": ("output_tokens", "completion_tokens", "outputTokens"),
        "total_tokens": ("total_tokens", "totalTokens"),
        "cached_tokens": ("cached_tokens", "cache_read_tokens", "cachedInputTokens"),
        "cache_write_tokens": ("cache_creation_input_tokens", "cache_write_tokens", "cacheCreationInputTokens"),
        "reasoning_tokens": ("reasoning_tokens", "thinking_tokens", "reasoningTokens"),
        "context_tokens": ("context_tokens", "current_context_tokens", "contextTokens"),
    }
    out = {key: _int_or_none(_nested(usage_obj, names)) for key, names in aliases.items()}
    if out["total_tokens"] is None and out["input_tokens"] is not None and out["output_tokens"] is not None:
        out["total_tokens"] = out["input_tokens"] + out["output_tokens"]
    return out


def _extract_texts(value: Any, inherited_role: str | None = None) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        role = str(value.get("role") or inherited_role or "unknown")
        for key in _TEXT_KEYS:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                found.append((role, item))
        for item in value.values():
            if isinstance(item, (dict, list)):
                found.extend(_extract_texts(item, role))
    elif isinstance(value, list):
        for item in value:
            found.extend(_extract_texts(item, inherited_role))
    return found[:50]


def _extract_tools(raw: dict[str, Any], session_id: str, turn_id: str, raw_event_id: str) -> list[dict[str, Any]]:
    tools = []
    for i, item in enumerate(_walk_dicts(raw)):
        name = item.get("tool") or item.get("tool_name") or item.get("name")
        if not name:
            continue
        output = item.get("output") or item.get("result")
        output_text = output if isinstance(output, str) else None
        stats = _text_stats(output_text or "")
        tools.append({
            "tool_call_id": str(item.get("id") or _stable_id(raw_event_id, "tool", str(i))),
            "session_id": session_id, "turn_id": turn_id, "tool_name": str(name),
            "arguments_json": json.dumps(item.get("arguments") or item.get("input") or {}, ensure_ascii=False),
            "output_text": output_text, "status": str(item.get("status") or "") or None,
            "error": str(item.get("error") or "") or None,
            "duration_ms": _int_or_none(item.get("duration_ms")),
            "output_chars": stats["chars"], "output_bytes": stats["bytes"],
            "output_lines": stats["lines"], "content_hash": stats["hash"],
            "raw_event_id": raw_event_id,
        })
    return tools


def _extract_commands(raw: dict[str, Any], session_id: str, turn_id: str, raw_event_id: str) -> list[dict[str, Any]]:
    commands = []
    for i, item in enumerate(_walk_dicts(raw)):
        cmd = item.get("cmd") or item.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            continue
        if item.get("tool") and "shell" not in str(item.get("tool")).lower() and "exec" not in str(item.get("tool")).lower():
            continue
        stdout = item.get("stdout") if isinstance(item.get("stdout"), str) else ""
        stderr = item.get("stderr") if isinstance(item.get("stderr"), str) else ""
        combined = stdout + ("\n" if stdout and stderr else "") + stderr
        stats = _text_stats(combined)
        commands.append({
            "command_id": _stable_id(raw_event_id, "command", str(i), cmd),
            "session_id": session_id, "turn_id": turn_id, "command": cmd,
            "cwd": str(item.get("cwd") or "") or None,
            "exit_code": _int_or_none(item.get("exit_code") or item.get("exitCode")),
            "stdout_text": stdout or None, "stderr_text": stderr or None,
            "output_chars": stats["chars"], "output_bytes": stats["bytes"],
            "output_lines": stats["lines"], "content_hash": stats["hash"],
            "raw_event_id": raw_event_id,
        })
    return commands


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _nested(obj: Any, names: tuple[str, ...]) -> Any:
    if not isinstance(obj, dict):
        return None
    for name in names:
        if name in obj:
            return obj[name]
    return None


def _find_key(value: Any, names: set[str]) -> Any:
    for item in _walk_dicts(value):
        for key, val in item.items():
            if key in names:
                return val
    return None


def _first_str(raw: dict[str, Any], names: tuple[str, ...]) -> str | None:
    value = _nested(raw, names)
    return value if isinstance(value, str) else None


def _normalize_ts(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except ValueError:
        return value


def _merge_session(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if old is None:
        return new
    merged = old.copy()
    merged["raw_event_count"] = int(old.get("raw_event_count") or 0) + 1
    for key in ("ended_at_utc", "model", "project_path"):
        merged[key] = new.get(key) or merged.get(key)
    for key in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"):
        if new.get(key) is not None:
            merged[key] = new[key]
    if new.get("token_quality") == "reported":
        merged["token_quality"] = "reported"
    return merged


def _text_stats(text: str) -> dict[str, Any]:
    return {
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "lines": text.count("\n") + (1 if text else 0),
        "hash": _sha(text),
    }


def _estimate_tokens(text: str) -> int | None:
    if not text:
        return None
    return max(1, round(len(text) / 4))


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _preview(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip()[:240]


def _context_category(role: str) -> str:
    return {
        "user": "user",
        "assistant": "previous_assistant_messages",
        "system": "system",
        "developer": "developer",
        "tool": "tool_results",
    }.get(role, "other")


def _provider_for(agent: str) -> str | None:
    return {"claude": "anthropic", "codex": "openai", "free_ai": "free_ai", "antigravity": "google"}.get(agent)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8", errors="replace")).hexdigest()[:32]


def _report_markdown(overview: dict[str, Any]) -> str:
    counts = overview.get("counts", {})
    return "\n".join([
        "# Token Forensics Export",
        "",
        "Generated locally with zero model-generation requests.",
        "",
        "## Counts",
        *(f"- {key}: {value}" for key, value in counts.items()),
    ])
