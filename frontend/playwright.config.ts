import { defineConfig, devices } from '@playwright/test'

// e2e always runs against the FAKE adapters (CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS=1)
// so it never touches a real ~/.claude, ~/.codex, or spawns codex.exe.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8788',
    trace: 'retain-on-failure',
  },
  webServer: {
    command:
      'cd ../backend && uv run uvicorn claude_codex_monitor.app:create_app --factory --host 127.0.0.1 --port 8788',
    url: 'http://127.0.0.1:8788/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      CLAUDE_CODEX_MONITOR_FAKE_ADAPTERS: '1',
      CCM_DATA_DIR: process.env.CCM_E2E_DATA_DIR ?? '',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
