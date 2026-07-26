<!-- CLAUDE-HANDOFF:ACTIVE -->

# Claude Code Agent Handover

## Objective
Build production-quality local usage dashboard (FastAPI+SQLite backend, React+TS+Vite+Tailwind+Recharts frontend) at I:\Projects\Automation\ClaudeCodexMonitor\1 that auto-discovers Claude Code + Codex profiles on this Windows machine, shows real usage/limits with verified/derived/estimated/stale/unavailable labeling, never fabricates data, single port 8787 prod-local mode. Full spec in original task prompt (12 build phases).

## Current status
Backend (phases 1-6 of build order) COMPLETE and verified against real machine
data. Toolchain switched mid-build per user instruction: Python env/deps now
via `uv` (NOT pixi - pixi.toml/pixi.lock/.pixi removed). Frontend will use
pnpm (not yet started).

Real discovery verified live: 4 Claude profiles (default/.claude, mt, nc,
personal via ps-profile), 1 Codex profile (default/.codex). Claude usage
reads sibling claude-usage-notifier DB at %LOCALAPPDATA%\ClaudeUsageNotifier\
(real data present, correctly labeled STALE since >6h old - never fabricated).
Codex usage does a REAL live app-server probe (spawned codex.exe, got verified
5.0% primary window). Full API smoke-tested via TestClient: health, discovery,
profiles, refresh-all, summary, settings get/patch, history delete with
confirm-gate - all working.

## Completed work
- Read both reference sibling projects in full (read-only, not modified):
  claude-usage-notifier (discovery/models/collector/state_store/paths/timezones)
  and ai_usage_notifier (discovery/models/codex_app_server/state_store).
- Backend scaffold + core: paths.py, timezones.py, config.py.
- Vendored + adapted: vendor/claude_statusline/{discovery,models,state_reader}.py,
  vendor/codex_appserver/{discovery,models,app_server_client}.py - each with
  "Adapted from ..." provenance comment.
- Domain models: models/{usage,profile,settings,diagnostics}.py (DataQuality
  enum verified/derived/estimated/stale/unavailable, UsageLevel enum, UsageLimit,
  ForecastResult, ProfileStatus, sanitize_path, Settings/SettingsPatch).
- Adapters: adapters/base.py (Protocol), claude_adapter.py (reads sibling DB
  read-only), codex_adapter.py (spawns codex app-server live, isolated env).
- DB: db/schema.sql + db/store.py (SQLite WAL, profiles/usage_snapshots/
  settings/refresh_log/sent_notifications tables; retention sweep + manual
  delete both always log to refresh_log before deleting).
- Services: discovery_service, usage_service (orchestrates fetch/parse/
  persist/notify + consecutive-failure tracking), history_service (reset-cycle
  boundary detection - never treats a reset drop as negative consumption),
  forecast_service (linear extrapolation, always ESTIMATED, needs >=3 verified
  snapshots in current cycle), settings_service, diagnostics_service,
  notification_service (win11toast, dedup via sent_notifications table,
  degrades to no-op log line if win11toast unavailable).
- scheduler.py: asyncio background loop, startup discover+refresh, periodic
  refresh, single asyncio.Lock (no overlap), exponential backoff w/ jitter on
  failure (cap 15min).
- API: routers for health/providers/profiles/discovery/history/summary/
  settings/diagnostics, all mounted under /api in app.py. app.py binds via
  uvicorn 127.0.0.1 (launcher will enforce this explicitly), mounts
  static/ dir for built frontend (StaticFiles) when present.
- Tests: backend/tests/{conftest.py, fixtures/*, unit/*.py (10 files), api/
  test_endpoints.py} - 54 tests total, all passing. Covers: Claude statusline
  parsing/models, Claude+Codex discovery (dedup, precedence, safe_label,
  PowerShell parsing), Codex app-server client (isolated env, account label,
  rate limit parsing incl. missing-secondary-window), Claude+Codex adapters
  (never-fabricate behavior), history reset-cycle detection, retention +
  manual delete confirm gating, forecast service, sanitize_path, settings
  service, and 10 API endpoint tests.
- Lint/type-check: `uv run ruff check src tests` -> All checks passed.
  `uv run pyright src` -> 0 errors, 0 warnings.

## Files changed
Backend tree under I:\Projects\Automation\ClaudeCodexMonitor\1\backend\src\claude_codex_monitor\
(see architecture section of original task prompt for full layout - all files
present matching that layout except services/README-type docs, which come
later). Tests under backend\tests\. Root: .gitignore, .env.example,
backend/pyproject.toml (uv-managed), backend/uv.lock, backend/.venv (gitignored).
pixi.toml/pixi.lock/.pixi REMOVED per toolchain change.

## Commands and tests run
- `uv venv --python 3.12` + `uv pip install -e ".[dev,notify]"` in backend/ - OK.
- `uv run pytest tests -q` -> 54 passed.
- `uv run ruff check src tests` -> All checks passed (after fixing E741/B007/
  E501/UP042 issues; line-length raised to 110, B008/UP042 ignored as
  intentional FastAPI-DI / pydantic-compat patterns).
- `uv run pyright src` -> 0 errors (fixed 4 real typing issues: adapters dict
  typed as ProviderAdapter protocol, lastrowid Optional guard, datetime
  comparison None-guard in history_service).
- Manual live smoke tests (ad-hoc scripts, since removed, using temp
  CCM_DATA_DIR): Claude discovery found 4 profiles matching predicted ground
  truth; Codex discovery found 1 profile; Claude fetch_usage against real
  sibling DB returned STALE readings (real numbers, correctly aged); Codex
  fetch_usage spawned real codex.exe app-server and got VERIFIED 5.0% primary.
  Full FastAPI TestClient smoke run of all major endpoints - all 200/400/404
  as expected.

## Current failures or blockers
None. Backend phase fully green.

## Decisions and assumptions
- TOOLCHAIN (per mid-build user instruction): Python env/deps via `uv`
  (uv venv + uv pip install -e, backend/pyproject.toml + backend/uv.lock),
  NOT pixi. pixi.toml/pixi.lock/.pixi.toml removed from repo root. Frontend
  will use pnpm exclusively (not npm/yarn). start-dashboard.ps1 (not yet
  written) must validate `uv` and `pnpm` on PATH and use `uv run uvicorn ...`
  + `pnpm install`/`pnpm build`, per the coordinator's explicit instruction.
  README must document uv+pnpm, not pixi.
- Claude adapter reads the sibling claude-usage-notifier's real DB read-only
  (plus narrow reset_confirmed write-back capability, not yet wired into a
  call site - state_reader.mark_reset_confirmed_seen exists but unused so far;
  low priority, can wire into history_service reset-boundary handling later
  if time permits).
- Codex adapter does live on-demand app-server probing every refresh (no
  caching layer beyond the history DB itself) - 18s timeout per profile.
- profile_key format is "provider:profile_id" everywhere (DB PK, API params).
- Ruff config: line-length=110, ignore B008 (FastAPI Depends pattern) and
  UP042 (kept `class X(str, Enum)` over StrEnum for broad compat).

## Exact next steps
1. Frontend scaffold: `pnpm create vite frontend -- --template react-ts` in
   I:\Projects\Automation\ClaudeCodexMonitor\1\, then add Tailwind (dark mode
   class strategy), Recharts, @tanstack/react-query.
2. src/api/client.ts + src/types/usage.ts mirroring backend Pydantic models
   (UsageLimit, ProfileStatus, Settings, ForecastResult, DiagnosticsRecord).
3. Layout components (Header, SummaryCards), Provider section + ProfileCard +
   UsageBar (Normal/Moderate/High/Critical/Exhausted/Unknown - text+icon+%,
   not color alone), History panel + Recharts charts w/ reset-boundary
   markers + range filters, Diagnostics drawer, common components
   (StatusBadge, CountdownTimer, ThemeToggle, SkeletonCard, EmptyState).
4. Hooks via React Query: useSummary/useProfiles/useHistory/useRefresh.
   Vite dev proxy -> http://127.0.0.1:8787 for /api during `pnpm dev`.
5. Settings UI + theme toggle wired to GET/PATCH /api/settings.
6. Wire real refresh-all/per-profile refresh buttons, auto-refresh toggle.
7. vitest unit tests (loading/empty/error states, ProfileCard, UsageBar,
   history filters, theme switching, basic a11y) + Playwright e2e (needs
   CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1 env flag wired into app.py's adapter
   construction so e2e never touches real ~/.claude or spawns codex.exe -
   NOT YET IMPLEMENTED, must add a fake adapter pair + branch in
   discovery_service/app.py construction before e2e tests can be written).
8. start-dashboard.ps1: validate uv + pnpm on PATH, build frontend if stale,
   copy frontend/dist -> backend/src/claude_codex_monitor/static/, start
   backend via `uv run uvicorn claude_codex_monitor.app:create_app --factory
   --host 127.0.0.1 --port 8787` (or `uv run` a wrapper task), poll
   /api/health until 200, open browser, clean shutdown, -Rebuild/-NoBrowser/-Port.
9. README.md + docs (architecture, security model, DB schema, API summary,
   provider adapter doc, troubleshooting).
10. Final full test run (pytest/vitest/playwright/ruff/pyright/eslint/tsc),
    fix failures, final commit, mark HANDOFF COMPLETE.

## Risks and warnings
- Do not modify anything under I:\Projects\Automation\Claude\Notifications\ or
  I:\Projects\Automation\Codex\Notifications\ (read-only reference - confirmed
  untouched so far).
- Never fabricate usage numbers; missing = Unavailable + reason (verified
  behavior in adapters + tests).
- Bind 127.0.0.1 only, never 0.0.0.0 - app.py itself doesn't bind (FastAPI
  object only); the actual bind happens in the uvicorn invocation in
  start-dashboard.ps1 / pyproject scripts - MUST double check that invocation
  explicitly passes --host 127.0.0.1 when written.
- CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS flag is referenced in config.py
  (fake_adapters_enabled()) but NOT YET WIRED into app.py's service
  construction - e2e tests will touch real ~/.claude and spawn real codex.exe
  until this is added. Must fix before writing Playwright e2e tests.
- backend/.venv and backend/uv.lock are real, in-place - do not delete
  backend/.venv casually, re-running `uv sync`/`uv pip install -e ".[dev,notify]"`
  from backend/ recreates it.

## Repository state
2 commits so far: (1) initial backend scaffold+services+API (created while
pixi was still in use, pixi.toml/lock included in that commit and later
deleted by the toolchain-switch - the delete is NOT yet committed as of this
handoff update). Working tree currently has: pixi.toml/pixi.lock/.pixi
deletions (staged for removal), .gitignore edit (removed .pixi/ line),
backend/pyproject.toml edits (uv-compatible, ruff config tweaks), several
backend/src edits (ruff/pyright fixes), backend/uv.lock (new, untracked),
backend/.venv (untracked, gitignored). Run `git status --short` to confirm
before next commit.

## Session information
Running as a single continuous foreground agent session (no subagents spawned
for backend; frontend may be delegated to a parallel background agent next
if scope warrants). No special env profile in use.

## Last updated
2026-07-27 00:40 (local, Asia/Dhaka assumed per spec default)
