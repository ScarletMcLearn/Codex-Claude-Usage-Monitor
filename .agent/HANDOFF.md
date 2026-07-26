<!-- CLAUDE-HANDOFF:ACTIVE -->

# Claude Code Agent Handover

## Objective
Build production-quality local usage dashboard (FastAPI+SQLite backend, React+TS+Vite+Tailwind+Recharts frontend) at I:\Projects\Automation\ClaudeCodexMonitor\1 that auto-discovers Claude Code + Codex profiles on this Windows machine, shows real usage/limits with verified/derived/estimated/stale/unavailable labeling, never fabricates data, single port 8787 prod-local mode. Full spec in original task prompt (12 build phases).

## Current status
Just starting implementation. Read both reference sibling projects in full:
- I:\Projects\Automation\Claude\Notifications\claude-usage-notifier\src\claude_usage_notifier\ (discovery.py, models.py, collector.py, state_store.py, paths.py, timezones.py)
- I:\Projects\Automation\Codex\Notifications\src\ai_usage_notifier\ (discovery.py, models.py, codex_app_server.py, state_store.py)
Both READ ONLY, not modified. Understood structures fully, ready to port/adapt into vendor/ dirs.

Directory scaffold created under backend/src/claude_codex_monitor/{vendor/claude_statusline,vendor/codex_appserver,models,adapters,services,db,api/routers,static} and backend/tests/{fixtures,unit,api}.

## Completed work
- Verified tools on PATH: pixi 0.70.1, node v22.18.0, pnpm 10.28.2, python 3.13.5 (system).
- Read reference projects (see above).
- Created directory scaffold.

## Files changed
None yet beyond this HANDOFF.md and directory scaffold (empty dirs).

## Commands and tests run
- `pixi --version`, `node --version`, `pnpm --version`, `python --version` — all OK.
- `git status` in target dir — empty repo, no commits yet, only .claude/ untracked.

## Current failures or blockers
None yet.

## Decisions and assumptions
- Following architecture exactly as specified in task prompt.
- Will vendor discovery.py/models.py/collector.py/state_store.py logic from claude-usage-notifier into vendor/claude_statusline/, and discovery.py/models.py/codex_app_server.py from ai_usage_notifier into vendor/codex_appserver/, each with adaptation comment header.
- Python 3.13 system available; pixi will manage its own env per pixi.toml (python only, not node).
- Windows notifications: will try win11toast first via pip.

## Exact next steps
1. Write pixi.toml, pyproject.toml, .gitignore, .env.example at repo root.
2. Vendor claude_statusline + codex_appserver modules.
3. Write domain models (models/usage.py DataQuality enum + UsageLimit, models/settings.py, models/profile.py, models/diagnostics.py).
4. Write adapters/base.py + claude_adapter.py + codex_adapter.py.
5. Write db/schema.sql + db/store.py.
6. Write services (discovery/usage/history/settings/diagnostics/notification/forecast).
7. Write scheduler.py.
8. Write api/routers/* + app.py wiring, mount under /api, bind 127.0.0.1:8787.
9. pytest unit+api tests with hand-written sanitized fixtures.
10. Frontend scaffold (Vite React TS + Tailwind), core components, hooks, wire to API.
11. History charts, diagnostics drawer, settings UI, notifications.
12. start-dashboard.ps1 launcher.
13. Run all test suites + linters, fix failures.
14. README.md + docs.
15. Git commits per phase.

## Risks and warnings
- Do not modify anything under I:\Projects\Automation\Claude\Notifications\ or I:\Projects\Automation\Codex\Notifications\ (read-only reference).
- Never fabricate usage numbers; missing = Unavailable + reason.
- Bind 127.0.0.1 only, never 0.0.0.0.
- No shell=True / string-concatenated subprocess calls; structured args + explicit per-profile env + timeouts only.

## Repository state
No commits yet. Only .agent/ and empty scaffold dirs untracked so far.

## Session information
Running as background/foreground agent task, no special env profile.

## Last updated
2026-07-27 00:15 (local, Asia/Dhaka assumed per spec default)
