from __future__ import annotations

import json
import sqlite3

from claude_codex_monitor.db.store import Store


MARKERS = [
    "CCM_LIVE_20260913112017_CLAUDE_DEFAULT",
    "CCM_LIVE_20260913112017_CLAUDE_MT",
    "CCM_LIVE_20260913112017_CLAUDE_NC",
    "CCM_LIVE_20260913112017_CLAUDE_PERSONAL",
    "CCM_LIVE_20260913112017_CODEX_DEFAULT_RETRY2",
    "CCM_LIVE_20260913112017_ANTIGRAVITY_DEFAULT",
    "CCM_LIVE_20260913112017_ANTIGRAVITY_CLI_PROJECT",
    "CCM_LIVE_20260913112017_FREE_AI_DEFAULT",
]


def main() -> None:
    con = sqlite3.connect(Store().path)
    con.row_factory = sqlite3.Row
    for marker in MARKERS:
        pattern = f"%{marker}%"
        rows = con.execute(
            """
            SELECT
                s.agent,
                s.model,
                s.project_path,
                s.session_id,
                COALESCE(s.ended_at_utc, s.started_at_utc) AS ts,
                s.total_tokens,
                s.token_quality,
                SUM(CASE WHEN m.role = 'user' AND m.text LIKE ? THEN 1 ELSE 0 END) AS user_hits,
                SUM(CASE WHEN m.role = 'assistant' AND m.text LIKE ? THEN 1 ELSE 0 END) AS assistant_hits,
                COUNT(m.message_id) AS messages
            FROM forensic_sessions s
            JOIN forensic_messages m ON m.session_id = s.session_id
            WHERE m.text LIKE ?
            GROUP BY s.session_id
            ORDER BY ts DESC
            LIMIT 8
            """,
            (pattern, pattern, pattern),
        ).fetchall()
        print(json.dumps({"marker": marker, "rows": [dict(row) for row in rows]}, ensure_ascii=False))
        raw_rows = con.execute(
            """
            SELECT
                s.agent,
                s.model,
                s.project_path,
                s.session_id,
                COALESCE(s.ended_at_utc, s.started_at_utc) AS ts,
                COUNT(r.raw_event_id) AS raw_hits
            FROM forensic_sessions s
            JOIN forensic_raw_events r ON r.session_id = s.session_id
            WHERE r.raw_json LIKE ?
            GROUP BY s.session_id
            ORDER BY ts DESC
            LIMIT 8
            """,
            (pattern,),
        ).fetchall()
        print(
            json.dumps(
                {"marker": marker, "raw_rows": [dict(row) for row in raw_rows]},
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
