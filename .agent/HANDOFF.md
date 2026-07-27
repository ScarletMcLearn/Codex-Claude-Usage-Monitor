<!-- CODEX-HANDOFF:COMPLETE -->

# Codex Agent Handover

## Objective

Fix dashboard freshness mismatch and add a usage report that calls each provider source and reports what it can prove.

## Current status

Freshness follow-up complete. Dashboard had prior implementation for live Claude usage and usage report; current fix adds stronger UI auto-update behavior for stats/history without manual browser/app refresh.

## Completed work

- User confirmed implementing TTY `/usage` probe is OK.
- Confirmed Claude CLI 2.1.220 has no direct usage/rate-limit command (`claude --help`, `claude auth --help`, `claude doctor --help`).
- Manual TTY probe with `claude` in repo and `C:\Users\getra` hit Claude trust gate. Chose not to auto-approve.
- Found safer command: `claude -p /usage --output-format json` runs the slash command without TUI trust prompt and with zero API turns/cost.
- Added parser for current Claude `/usage` output:
  - `Current session: N% used - resets ...` -> `five_hour`
  - `Current week (all models): N% used - resets ...` -> `seven_day`
  - fallback patterns for explicit `5-hour`, `7-day`, `% remaining`, and `fully used`.
- Wired Claude adapter to prefer `/usage` when parseable, mark limits `verified`, include parsed reset times, and fall back to statusline DB if command fails/no parse.
- Updated usage report source/message for Claude `/usage` and fallback.
- Live verification after restart: default Claude reported `12%` 5-hour reset `2026-07-27T08:10:00Z`, `2%` 7-day reset `2026-08-03T04:00:00Z`, source `claude /usage live command`, quality `verified`.
- Live summary after `POST /api/refresh-all`: `queried_successfully: 5`, `stale_or_failed: 0`, next reset `2026-07-27T08:10:00+00:00`.
- Confirmed Claude dashboard source is `ClaudeUsageNotifier` statusline DB. Default profile last captured `84%` at `2026-07-27T02:34:28+06`, so dashboard cannot infer later `100%` without a newer statusline payload.
- Changed Claude freshness: statusline DB rows older than 10m become `stale`, not `verified`, with reason shown in UI.
- Added `POST /api/usage-report`: actively checks every discovered active profile without persisting snapshots.
- Report behavior: Codex uses live `codex app-server` probe; Claude uses latest captured statusline DB snapshot and reports that no direct Claude CLI usage command is available.
- Added dashboard `Usage report` button in header and report panel with profile/source/window/used/quality/message rows.
- Restarted dashboard on port 8787 with rebuilt frontend/static assets.
- Live `/api/usage-report` verification: 5 profiles checked; all Claude rows stale with source note; Codex row verified from live app-server (`12%` at verification time).
- Added `cache: 'no-store'` to frontend API requests so browser/proxy cache cannot serve stale stats.
- Added 15s polling to `useHistory` so chart/stats history follows backend scheduler refreshes.
- Updated refresh mutations to write returned limits into `limits-all` query cache immediately before invalidation, so refresh-all/profile refresh updates usage bars without waiting for follow-up GET.

## Files changed

- `backend/src/claude_codex_monitor/adapters/claude_adapter.py`: 10m Claude freshness and clear stale reason.
- `backend/src/claude_codex_monitor/vendor/claude_usage_command.py`: new live Claude `/usage` command runner and parser.
- `backend/src/claude_codex_monitor/api/routers/profiles.py`: new `/api/usage-report` endpoint.
- `backend/tests/api/test_endpoints.py`: usage-report and summary regression tests.
- `backend/tests/unit/test_claude_adapter.py`: freshness policy tests.
- `backend/tests/unit/test_claude_usage_command.py`: `/usage` parser tests.
- `frontend/src/App.tsx`: refresh orchestration plus usage report state/action/panel.
- `frontend/src/api/client.ts`: `usageReport()` API call.
- `frontend/src/api/client.ts`: all API fetches use `cache: 'no-store'`.
- `frontend/src/components/layout/Header.tsx`: `Usage report` button.
- `frontend/src/components/layout/UsageReportPanel.tsx`: new report UI.
- `frontend/src/components/providers/UsageBar.tsx`: show stale reason text.
- `frontend/src/hooks/useRefresh.ts`: invalidate `limits-all` after refresh.
- `frontend/src/hooks/useRefresh.ts`: seed `limits-all` cache from refresh mutation responses.
- `frontend/src/hooks/useHistory.ts`: poll history every 15s.
- `frontend/src/test/setup.ts`: jsdom `matchMedia` stub.
- `frontend/src/types/usage.ts`: usage report types.
- `frontend/src/App.test.tsx`: app refresh/report tests.
- `.agent/HANDOFF.md`: operational checkpoint.

## Commands and tests run

- `claude --help`, `claude auth --help`, `claude doctor --help`.
- SQLite read against `%LOCALAPPDATA%\ClaudeUsageNotifier\state\usage_state.sqlite3` with escalation.
- `uv run pytest tests/unit/test_claude_adapter.py`: 5 passed.
- `pnpm run test -- src/components/providers/UsageBar.test.tsx`: 5 passed.
- `uv run pytest tests/api/test_endpoints.py -q`: 11 passed, 1 warning.
- `pnpm run test -- src/App.test.tsx`: 5 passed.
- `pnpm run test -- src/App.test.tsx`: first run had transient fake-timer timeout in first test; immediate targeted retry passed, then full suite passed 5/5.
- `pnpm run build`: failed in sandbox with `spawn EPERM` loading native Tailwind oxide.
- Escalated `pnpm run build`: passed; Vite emitted only existing large chunk warning.
- `uv run pytest`: 57 passed, 1 warning.
- `uv run pytest -q`: 64 passed, 1 warning.
- `pnpm run test`: 35 passed.
- `pnpm run lint`: passed.
- `pnpm run build`: passed.
- `pixi run lint-backend`: passed after line-length fix.
- `pixi run typecheck-backend`: 0 errors.
- `uv run ruff check src tests`: passed.
- `uv run pyright src`: 0 errors.
- Restarted dashboard process and verified `POST http://127.0.0.1:8787/api/usage-report` works.

## Current failures or blockers

No code/test blockers. Claude `/usage` output is not a formal stable API; parser may need update if Claude changes wording.

## Decisions and assumptions

- Use `claude -p /usage --output-format json`, not a dummy assistant prompt. Current observed command returns zero API turns/cost for slash usage.
- Report should be honest about source per provider.
- Report endpoint should not persist snapshots/history.

## Exact next steps

Optional: commit implementation files, excluding `.agent/HANDOFF.md` and unrelated `?? .claude/`.

## Risks and warnings

- Claude `/usage` parser is best-effort against CLI text, not a guaranteed API contract.
- Codex report does a real subprocess probe and may take seconds.
- Existing untracked `.claude/` in repo left untouched.

## Repository state

`git status --short`: modified `.agent/HANDOFF.md`, backend adapter/router/tests, frontend app/client/header/usage bar/hooks/types/tests/setup; untracked `.claude/`, `backend/src/claude_codex_monitor/vendor/claude_usage_command.py`, `backend/tests/unit/test_claude_usage_command.py`, `frontend/src/App.test.tsx`, `frontend/src/components/layout/UsageReportPanel.tsx`.

`git diff --stat` tracked files: 13 files changed, 495 insertions(+), 167 deletions(-). Untracked new files not included in that stat.

## Last updated

2026-07-27T21:54:07+06:00
