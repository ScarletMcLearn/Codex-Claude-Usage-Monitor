from __future__ import annotations

from claude_codex_monitor.services.token_accounting import (
    TokenCounterSemantics,
    TokenMetric,
    derive_cumulative_deltas,
)


def metric(value: int, event: str) -> TokenMetric:
    return TokenMetric(
        name="input_tokens",
        value=value,
        semantics=TokenCounterSemantics.CUMULATIVE_SESSION,
        quality="reported",
        source_event_id=event,
        parser_version="test",
    )


def test_cumulative_to_delta_prevents_double_counting():
    rows = derive_cumulative_deltas([metric(30_000, "e1"), metric(50_000, "e2"), metric(80_000, "e3")])

    assert [row["delta"] for row in rows] == [30_000, 20_000, 30_000]
    assert sum(row["delta"] or 0 for row in rows) == 80_000
    assert all(row["quality"] == "derived" for row in rows)


def test_duplicate_cumulative_event_generates_no_delta():
    rows = derive_cumulative_deltas([metric(30_000, "e1"), metric(30_000, "e1")])

    assert [row["delta"] for row in rows] == [30_000, None]
    assert rows[1]["derivation_method"] == "duplicate_cumulative_snapshot"


def test_counter_reset_never_generates_negative_delta():
    rows = derive_cumulative_deltas([
        metric(80_000, "e1"),
        metric(95_000, "e2"),
        metric(12_000, "e3"),
        metric(30_000, "e4"),
    ])

    assert [row["delta"] for row in rows] == [80_000, 15_000, 12_000, 18_000]
    assert rows[2]["derivation_method"] == "cumulative_reset"


def test_decrease_can_be_ignored_when_reset_not_authorized():
    rows = derive_cumulative_deltas([metric(80_000, "e1"), metric(12_000, "e2")], reset_on_decrease=False)

    assert rows[1]["delta"] is None
    assert rows[1]["derivation_method"] == "out_of_order_or_decrease_ignored"


def test_mixed_non_cumulative_metric_passes_through():
    rows = derive_cumulative_deltas([
        TokenMetric(
            name="output_tokens",
            value=25,
            semantics=TokenCounterSemantics.PER_REQUEST,
            quality="reported",
            source_event_id="e1",
            parser_version="test",
        )
    ])

    assert rows[0]["delta"] == 25
    assert rows[0]["semantics"] == "per_request"
