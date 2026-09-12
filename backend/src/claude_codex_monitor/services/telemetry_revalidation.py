"""Read-only structural telemetry validation.

No model APIs, no provider commands, no prompt/output printing.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def revalidate_jsonl_roots(roots: list[Path], *, max_files: int = 200) -> dict[str, Any]:
    files = []
    event_types: Counter[str] = Counter()
    token_fields: Counter[str] = Counter()
    structural_hash = hashlib.sha256()
    events = messages = tools = relationships = 0
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl"))[:max_files]:
            if not path.is_file():
                continue
            file_events = 0
            with path.open("rb") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        raw = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(raw, dict):
                        continue
                    file_events += 1
                    events += 1
                    event_type = str(raw.get("type") or raw.get("event") or "unknown")
                    event_types[event_type] += 1
                    structural_hash.update(event_type.encode("utf-8", errors="replace"))
                    structural_hash.update(b"\0")
                    message = raw.get("message")
                    payload = raw.get("payload")
                    if isinstance(message, dict):
                        messages += 1
                        _count_usage_fields(message.get("usage"), token_fields)
                        if isinstance(message.get("content"), list):
                            tools += sum(
                                1 for item in message["content"]
                                if isinstance(item, dict)
                                and item.get("type") in {"tool_use", "tool_result"}
                            )
                    if isinstance(payload, dict):
                        messages += 1 if payload.get("type") == "message" else 0
                        _count_usage_fields(payload.get("usage") or payload.get("info"), token_fields)
                        if str(payload.get("type") or "").endswith("tool_call"):
                            tools += 1
                    if raw.get("parentUuid") or raw.get("isSidechain"):
                        relationships += 1
            files.append({"path_hash": _hash_path(path), "event_count": file_events})
    return {
        "file_count": len(files),
        "event_count": events,
        "message_count": messages,
        "tool_count": tools,
        "relationship_count": relationships,
        "event_type_names": sorted(event_types),
        "event_type_counts": dict(sorted(event_types.items())),
        "token_field_presence_counts": dict(sorted(token_fields.items())),
        "structural_hash": structural_hash.hexdigest(),
        "files": files,
        "model_generation_requests": 0,
    }


def _count_usage_fields(value: Any, counter: Counter[str]) -> None:
    if not isinstance(value, dict):
        return
    for key in value:
        if "token" in str(key).lower():
            counter[str(key)] += 1


def _hash_path(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8", errors="replace")).hexdigest()[:16]
