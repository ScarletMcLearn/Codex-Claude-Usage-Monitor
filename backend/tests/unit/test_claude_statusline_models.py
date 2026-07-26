from __future__ import annotations

from claude_codex_monitor.vendor.claude_statusline.models import StatusLinePayload
from tests.fixtures.claude_statusline_payloads import (
    FULL_PAYLOAD,
    MILLISECOND_RESET_PAYLOAD,
    NO_RATE_LIMITS_PAYLOAD,
    NULL_FIELDS_PAYLOAD,
    PARTIAL_PAYLOAD_FIVE_HOUR_ONLY,
)


def test_full_payload_parses_both_windows():
    payload = StatusLinePayload.parse(FULL_PAYLOAD)
    assert payload.had_rate_limits
    assert set(payload.windows) == {"five_hour", "seven_day"}
    assert payload.windows["five_hour"].used_percentage == 42.5


def test_partial_payload_only_has_five_hour():
    payload = StatusLinePayload.parse(PARTIAL_PAYLOAD_FIVE_HOUR_ONLY)
    assert set(payload.windows) == {"five_hour"}
    assert "seven_day" not in payload.windows


def test_no_rate_limits_is_not_an_error():
    payload = StatusLinePayload.parse(NO_RATE_LIMITS_PAYLOAD)
    assert not payload.had_rate_limits
    assert payload.windows == {}


def test_null_fields_produce_no_windows():
    payload = StatusLinePayload.parse(NULL_FIELDS_PAYLOAD)
    assert payload.session_id is None
    assert payload.windows == {}


def test_millisecond_reset_is_converted_to_seconds():
    payload = StatusLinePayload.parse(MILLISECOND_RESET_PAYLOAD)
    window = payload.windows["five_hour"]
    assert window.resets_at == 1_800_000_000  # converted from ms


def test_garbage_input_never_raises():
    assert StatusLinePayload.parse("not a dict").windows == {}
    assert StatusLinePayload.parse(None).windows == {}
    assert StatusLinePayload.parse(12345).windows == {}
