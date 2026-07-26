"""Hand-written, sanitized Codex app-server JSON-RPC style payloads for tests."""

ACCOUNT_AUTHENTICATED = {
    "account": {"type": "chatgpt", "email": "sanitized-test@example.invalid", "planType": "plus"}
}

ACCOUNT_UNAUTHENTICATED = {"requiresOpenaiAuth": True}

RATE_LIMITS_PRIMARY_ONLY = {
    "rateLimits": {
        "limitId": "codex-usage",
        "limitName": "Weekly usage",
        "planType": "plus",
        "primary": {
            "windowDurationMins": 10080,
            "usedPercent": 37,
            "resetsAt": "2026-08-01T00:00:00Z",
        },
    }
}

RATE_LIMITS_BY_LIMIT_ID = {
    "rateLimitsByLimitId": {
        "codex-usage": {
            "limitId": "codex-usage",
            "planType": "plus",
            "primary": {"windowDurationMins": 10080, "usedPercent": 88, "resetsAt": "2026-08-01T00:00:00Z"},
            "secondary": {"windowDurationMins": 300, "usedPercent": 12, "resetsAt": "2026-07-27T00:00:00Z"},
        }
    }
}

RATE_LIMITS_EMPTY = {}
