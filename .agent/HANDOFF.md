<!-- CODEX-HANDOFF:ACTIVE -->

# Codex Agent Handover

## Objective
Fix monitor not recording local forensic logs after 2026-09-13 05:45:53.

## Current status
Active. User requested live end-to-end probe: call each discovered profile/provider, verify prompt/output appear in forensics sorted newest.

## Completed work
Loaded caveman skill per global instructions. Inspected repo root, git status, scheduler, app wiring, forensics router/service, and tests.

## Files changed
- `.agent/HANDOFF.md`: active progress record.
- `backend/src/claude_codex_monitor/scheduler.py`: optional `ForensicsService`; scheduler runs forensic refresh after usage refresh and logs/catches forensic failures separately.
- `backend/src/claude_codex_monitor/app.py`: passes `forensics_service` into scheduler.
- `backend/tests/unit/test_scheduler.py`: verifies scheduler runs forensics and does not fail quota refresh if forensic scan fails.
- `backend/src/claude_codex_monitor/services/forensics_service.py`: Codex session id now prefers rollout filename/session id for non-`session_meta` payloads; parser version bumped to v4.
- `backend/src/claude_codex_monitor/db/store.py`: added source-scoped forensic purge for parser-version reparses so old bad rows do not block corrected rows.
- `backend/tests/unit/test_forensics_service.py`: asserts Codex real-shape fixture stays grouped into one session.
- `backend/src/claude_codex_monitor/db/schema.sql`: added source-id/source-event indexes so recent reparse completes.
- `backend/src/claude_codex_monitor/services/forensics_service.py`: scans active `.claude-*` roots through Claude profile discovery, limits refresh to newest 20 JSONL sources for responsiveness.

## Commands and tests run
- `Get-Content C:\Users\getra\.codex\skills\caveman\SKILL.md` exit 0.
- `Get-ChildItem -Name` exit 0.
- `git status --short` exit 0: existing dirty files in backend/frontend tests/components.
- `rg ...` targeted searches exit 0.
- `Get-Content backend\src\claude_codex_monitor\scheduler.py` exit 0.
- `Get-Content backend\src\claude_codex_monitor\services\forensics_service.py` exit 0, truncated but enough for refresh path.
- `Get-Content backend\src\claude_codex_monitor\api\routers\forensics.py` exit 0.
- `Get-Content backend\src\claude_codex_monitor\app.py` exit 0.
- `uv run pytest tests/unit/test_scheduler.py tests/unit/test_forensics_service.py -q` exit 0 with escalation for uv cache access: 13 passed in 0.83s. Full output: `work\pytest-scheduler-forensics.log`.
- DB inspection showed latest `reported` Codex row at 2026-09-12T23:10:34Z, but latest `unknown` Codex rows at 2026-09-12T23:55:20Z with one-event ids like `msg_...`; confirms parser grouping bug.
- `uv run pytest tests/unit/test_forensics_service.py tests/unit/test_scheduler.py -q` exit 0 with escalation: 13 passed in 0.76s. Full output: `work\pytest-forensics-reparse.log`.
- Real refresh command failed with `sqlite3.OperationalError: database is locked`. Full output: `work\forensics-refresh-v4.log`.
- After index/source-limit fixes, real refresh succeeded: `sources_scanned=20`, `events_processed=5`; output `work\forensics-refresh-top20.log`.
- Browser verification: opened `http://127.0.0.1:8787`, clicked Token Forensics, clicked Refresh evidence. Sessions table first row: `13/09/2026, 10:58:48`, `claude`, `claude-sonnet-5`, project `H:\Projects\FullStack\Matchora\1`, `924`, `405`, `Reported`.

## Current failures or blockers
No blockers.

## Decisions and assumptions
Treat "logs" as forensic JSONL ingestion shown by Forensics UI/API. Existing user changes must not be reverted.

## Exact next steps
No required next steps.

## Risks and warnings
Do not touch existing dirty frontend files unless required. Forensics may scan many JSONL files; keep scheduler resilient.

## Repository state
Dirty files after this fix include:
- `M .agent/HANDOFF.md`
- `M backend/src/claude_codex_monitor/app.py`
- `M backend/src/claude_codex_monitor/db/schema.sql`
- `M backend/src/claude_codex_monitor/db/store.py`
- `M backend/src/claude_codex_monitor/scheduler.py`
- `M backend/src/claude_codex_monitor/services/forensics_service.py`
- `M backend/tests/unit/test_forensics_service.py`
- `?? backend/tests/unit/test_scheduler.py`

Pre-existing dirty files still present:
- `M backend/tests/api/test_endpoints.py`
- `M frontend/src/components/forensics/ForensicsPanel.test.tsx`
- `M frontend/src/components/forensics/ForensicsPanel.tsx`

## Last updated
2026-09-13T00:00:00+06:00
