from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TokenCounterSemantics(StrEnum):
    PER_REQUEST = "per_request"
    PER_TURN = "per_turn"
    CUMULATIVE_SESSION = "cumulative_session"
    CUMULATIVE_CONVERSATION = "cumulative_conversation"
    CURRENT_CONTEXT = "current_context"
    ACCOUNT_USAGE = "account_usage"
    QUOTA_ONLY = "quota_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TokenMetric:
    name: str
    value: int | None
    semantics: TokenCounterSemantics
    quality: str
    source_event_id: str
    parser_version: str


def derive_cumulative_deltas(
    metrics: list[TokenMetric], *, reset_on_decrease: bool = True
) -> list[dict[str, Any]]:
    """Turn ordered cumulative snapshots into usage deltas without double counting."""
    previous_by_name: dict[str, TokenMetric] = {}
    seen: set[tuple[str, str, int | None]] = set()
    rows: list[dict[str, Any]] = []
    cumulative = {
        TokenCounterSemantics.CUMULATIVE_SESSION,
        TokenCounterSemantics.CUMULATIVE_CONVERSATION,
    }
    for metric in metrics:
        if metric.value is None:
            continue
        dedupe_key = (metric.name, metric.source_event_id, metric.value)
        if dedupe_key in seen:
            rows.append(_row(metric, None, "duplicate_cumulative_snapshot", None))
            continue
        seen.add(dedupe_key)
        if metric.semantics not in cumulative:
            rows.append(_row(metric, metric.value, "reported_non_cumulative", None))
            previous_by_name[metric.name] = metric
            continue
        previous = previous_by_name.get(metric.name)
        if previous is None or previous.value is None:
            rows.append(_row(metric, metric.value, "initial_cumulative_sample", previous))
        elif metric.value >= previous.value:
            rows.append(_row(metric, metric.value - previous.value, "cumulative_delta", previous))
        elif reset_on_decrease:
            rows.append(_row(metric, metric.value, "cumulative_reset", previous))
        else:
            rows.append(_row(metric, None, "out_of_order_or_decrease_ignored", previous))
        previous_by_name[metric.name] = metric
    return rows


def _row(
    metric: TokenMetric,
    delta: int | None,
    method: str,
    previous: TokenMetric | None,
) -> dict[str, Any]:
    return {
        "source_metric": metric.name,
        "source_event_id": metric.source_event_id,
        "previous_source_event_id": previous.source_event_id if previous else None,
        "current_value": metric.value,
        "previous_value": previous.value if previous else None,
        "delta": delta,
        "quality": "derived" if method.startswith(("initial_", "cumulative_", "out_of")) else metric.quality,
        "semantics": metric.semantics.value,
        "derivation_method": method,
        "parser_version": metric.parser_version,
    }
