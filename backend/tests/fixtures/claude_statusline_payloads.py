"""Hand-written, sanitized Claude Code statusline JSON payloads for tests.
No real credentials or paths - purely synthetic fixture data.
"""

FULL_PAYLOAD = {
    "session_id": "test-session-0001",
    "version": "2.1.220",
    "rate_limits": {
        "five_hour": {"used_percentage": 42.5, "resets_at": 1_800_000_000},
        "seven_day": {"used_percentage": 10.0, "resets_at": 1_800_500_000},
    },
}

PARTIAL_PAYLOAD_FIVE_HOUR_ONLY = {
    "session_id": "test-session-0002",
    "version": "2.1.220",
    "rate_limits": {
        "five_hour": {"used_percentage": 99.0, "resets_at": 1_800_100_000},
    },
}

NO_RATE_LIMITS_PAYLOAD = {
    "session_id": "test-session-0003",
    "version": "2.1.220",
}

MALFORMED_JSON_TEXT = "{not-valid-json"

NULL_FIELDS_PAYLOAD = {
    "session_id": None,
    "version": None,
    "rate_limits": {
        "five_hour": {"used_percentage": None, "resets_at": None},
    },
}

MILLISECOND_RESET_PAYLOAD = {
    "session_id": "test-session-0004",
    "version": "2.1.220",
    "rate_limits": {
        "five_hour": {"used_percentage": 5.0, "resets_at": 1_800_000_000_000},  # ms, not s
    },
}
