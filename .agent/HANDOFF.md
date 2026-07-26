<!-- CLAUDE-HANDOFF:COMPLETE -->

# Claude Code Agent Handover

## Objective
Build production-quality local usage dashboard (FastAPI+SQLite backend,
React+TS+Vite+Tailwind+Recharts frontend) at
I:\Projects\Automation\ClaudeCodexMonitor\1 that auto-discovers Claude Code +
Codex profiles on this Windows machine, shows real usage/limits with
verified/derived/estimated/stale/unavailable labeling, never fabricates
data, single port 8787 prod-local mode.

## Current status
COMPLETE. All 12 build-order phases done. Full test suite green across both
stacks. Launcher script tested and working. README written.

## Completed work
- Read both reference sibling projects (read-only, never modified):
  claude-usage-notifier and ai_usage_notifier.
- Backend: FastAPI app, vendored+adapted discovery/models/state-reader for
  Claude and discovery/models/app-server-client for Codex, domain models
  (DataQuality/UsageLevel/UsageLimit/ProfileStatus/Settings/Diagnostics/
  ForecastResult), ProviderAdapter protocol + Claude/Codex/Fake adapters,
  SQLite store (WAL, profiles/usage_snapshots/settings/refresh_log/
  sent_notifications), 7 services (discovery/usage/history/settings/
  diagnostics/notification/forecast), asyncio background scheduler
  (no-overlap lock, backoff+jitter), 8 API routers mounted under /api,
  StaticFiles mount for built frontend.
- Frontend: Vite+React+TS+Tailwind v4+Recharts+React Query dashboard with
  Header/SummaryCards/ProviderSection/ProfileCard/UsageBar/HistoryPanel+
  Chart+Filters/DiagnosticsDrawer/common components, all wired to the real
  API via hooks.
- Tests: 54 pytest (unit+API), 29 vitest (component), 7 Playwright e2e
  (against FakeClaudeAdapter/FakeCodexAdapter via
  CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1) - all passing.
- Lint/typecheck: ruff clean, pyright 0 errors, oxlint clean, tsc -b clean.
- start-dashboard.ps1: validates pixi/uv/pnpm on PATH, builds frontend if
  stale, copies dist into backend static/, starts backend via
  `pixi run serve`, polls /api/health, opens browser, -Rebuild/-NoBrowser/
  -Port flags all implemented and manually tested.
- README.md: full architecture, security model, data-quality semantics,
  install/dev/prod instructions, discovery/usage-source explanation,
  troubleshooting, testing, DB/retention/deletion, API summary, adapter
  interface doc, known limitations.
- Found and fixed a REAL production bug during e2e testing: win11toast's
  toast() call blocks the calling thread ~10s per notification; a refresh
  triggering 3 notifications caused a 31-second hang on every /api/refresh-all
  call. Fixed by firing toasts on a daemon thread
  (services/notification_service.py). Verified fix: refresh-all now
  completes in ~65ms instead of 31s.

## Files changed
See git log - 6 commits total:
1. Backend scaffold+services+API (initial, pixi-based env - later migrated)
2. Backend: switch to uv toolchain, add 54 tests, fix ruff/pyright, fake adapters
3. Frontend: full React dashboard wired to real API; pixi restored as thin
   orchestrator over uv+pnpm
4. Fix win11toast blocking bug; add vitest+Playwright suites
5. Add start-dashboard.ps1 launcher; fix CCM_PORT threading
6. (this commit) README.md + final HANDOFF completion

High-level layout: backend/src/claude_codex_monitor/{app.py, config.py,
paths.py, timezones.py, models/, adapters/, vendor/{claude_statusline,
codex_appserver}, services/, scheduler.py, db/, api/routers/, static/}.
backend/tests/{conftest.py, fixtures/, unit/, api/}. frontend/src/{api/,
types/, components/{layout,providers,history,diagnostics,common}/, hooks/,
test/}. frontend/e2e/. Root: pixi.toml, README.md, .gitignore, .env.example,
start-dashboard.ps1.

## Commands and tests run (final verification pass)
- `pixi run test-backend` -> 54 passed.
- `pixi run lint-backend` -> All checks passed (ruff).
- `pixi run typecheck-backend` -> 0 errors, 0 warnings (pyright).
- `pixi run test-frontend` -> 29 passed (vitest).
- `pixi run lint-frontend` -> clean (oxlint).
- `pnpm exec tsc -b` (frontend) -> clean.
- `pixi run e2e-frontend` -> 7 passed (Playwright, fake adapters).
- start-dashboard.ps1 manually run as a real process (pwsh -File, not inside
  a PowerShell job - jobs have known native-process I/O capture quirks that
  are a test-harness artifact, not a script bug) with -NoBrowser -Port 8798:
  reached "Backend is healthy" and served both /api/health and / correctly;
  confirmed via Get-NetTCPConnection that only 127.0.0.1:8798 was listening.
- Manual live smoke test against REAL machine data (not fake adapters):
  discovered 4 real Claude profiles (default/.claude, mt, nc, personal) and
  1 real Codex profile (default/.codex); clicked Refresh all in the actual
  browser UI; Claude profiles showed real STALE readings from the sibling
  claude-usage-notifier DB (33-44% real numbers); Codex profile showed a
  REAL live app-server probe result (VERIFIED 5% primary window); history
  endpoint recorded 18 real snapshot rows; countdown timers correctly
  rendered Asia/Dhaka local time.

## Current failures or blockers
None. All tests green, no known bugs outstanding.

## Decisions and assumptions
- TOOLCHAIN (final, after two revisions): pixi.toml is a thin task
  orchestrator only (no `[dependencies]` beyond bare project metadata).
  Every task shells out to `uv` (backend/pyproject.toml + backend/uv.lock is
  the real Python dependency source of truth) or `pnpm` (frontend/
  package.json). End users and start-dashboard.ps1 run `pixi run <task>`
  only - never invoke uv/pnpm binaries directly. Verified working:
  `pixi run serve` correctly threads a custom CCM_PORT env var through to
  uvicorn's `--port` argument (pixi's task shell does NOT support bash-style
  `${VAR:-default}` syntax - plain `$VAR` works and the caller must set it
  first; start-dashboard.ps1 always sets `$env:CCM_PORT` before invoking).
- Claude adapter is read-only against the sibling claude-usage-notifier DB;
  does not register its own statusline hook (documented as a known
  limitation/tradeoff in README, given time constraints - the spec allowed
  prioritizing self-contained discovery + sibling-DB-read over a
  self-contained statusline hook).
- Codex adapter does live on-demand app-server probing every refresh (18s
  timeout), no additional caching layer beyond the history DB.
- profile_key format is "provider:profile_id" everywhere.
- Notification toasts fire on background daemon threads (critical fix -
  win11toast's synchronous call blocks ~10s per toast otherwise).
- Ruff: line-length=110, ignore B008 (FastAPI Depends pattern) and UP042
  (kept `class X(str, Enum)` over StrEnum for pydantic/FastAPI JSON compat).
- Frontend bundle is a single ~620KB JS chunk (not code-split) - noted as a
  minor optimization opportunity, not fixed given time constraints; the app
  is fully functional as-is and loads fast on localhost.

## Exact next steps (if anyone continues this)
Nothing required for correctness. Optional polish for a future session:
1. Wire ClaudeNotifierStateReader.mark_reset_confirmed_seen into
   history_service's reset-boundary detection so this dashboard also clears
   the sibling notifier's reset_confirmed flag once it has recorded the new
   cycle (currently unused, low priority).
2. Code-split the frontend bundle (dynamic import for Recharts/History panel)
   to shrink the single 620KB chunk if load time on a very slow machine
   becomes a concern.
3. Consider adding a lightweight in-app Claude statusline hook registration
   flow (opt-in) so the dashboard can be fully self-contained for Claude
   usage data without depending on the separate claude-usage-notifier tool.
4. Settings UI currently only exposes auto-refresh/interval/theme from the
   Header; a full Settings panel/modal for retention days, notification
   toggles, hide-sensitive-paths, and per-profile friendly names/enable-
   disable would be a nice addition (backend API already supports all of
   this via GET/PATCH /api/settings - only frontend UI surface is missing).

## Risks and warnings
- Do not modify anything under I:\Projects\Automation\Claude\Notifications\
  or I:\Projects\Automation\Codex\Notifications\ (read-only reference -
  confirmed untouched throughout).
- Never fabricate usage numbers; missing = Unavailable + reason (verified in
  both backend tests and frontend UsageBar tests).
- Bind 127.0.0.1 only - confirmed via netstat/Get-NetTCPConnection during
  testing, both for ad-hoc uvicorn runs and via start-dashboard.ps1.
- Before running `pnpm build` + copying to backend/static/, remember the
  static/ directory content is what start-dashboard.ps1's staleness check
  looks at - if you hand-edit frontend/dist without rebuilding via pnpm, the
  staleness check may not catch it (it compares frontend/src and index.html
  mtimes against frontend/dist, not backend/static/ directly - copying is a
  manual step inside the same script, so this is self-consistent as-is).
- backend/.venv, frontend/node_modules, .pixi/ are all real, gitignored,
  present on disk - do not delete casually; `pixi run sync` /
  `pixi run install-frontend` recreate them.

## Repository state
6 commits on branch master. Working tree clean except this final
HANDOFF.md update (about to be finalized) and README.md (about to be
committed alongside it). Run `git status --short` to confirm before any
further changes.

## Session information
Single continuous foreground agent session for the entire build (no
subagents spawned - all work done directly per task instructions not to
re-delegate the whole task). No special env profile in use beyond ad-hoc
CCM_DATA_DIR/CCM_PORT overrides used for isolated testing (all cleaned up).

## Last updated
2026-07-27 01:20 (local, Asia/Dhaka assumed per spec default)
