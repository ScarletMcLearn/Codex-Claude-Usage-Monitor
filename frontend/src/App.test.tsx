import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProfileStatus, Settings, Summary } from './types/usage'

const profiles: ProfileStatus[] = [
  {
    provider: 'claude',
    profile_id: 'claude-work',
    profile_key: 'claude:work',
    label: 'work',
    friendly_name: null,
    sanitized_source: '~/.claude-work',
    discovery_source: 'extra',
    is_active: true,
    is_authenticated: null,
    last_refresh_utc: '2026-07-26T19:00:00Z',
    last_success_utc: '2026-07-26T19:00:00Z',
    last_error: null,
    is_stale: false,
    executable_found: true,
  },
  {
    provider: 'claude',
    profile_id: 'claude-default',
    profile_key: 'claude:default',
    label: 'default',
    friendly_name: null,
    sanitized_source: '~/.claude',
    discovery_source: 'default',
    is_active: true,
    is_authenticated: null,
    last_refresh_utc: '2026-07-26T20:00:00Z',
    last_success_utc: '2026-07-26T20:00:00Z',
    last_error: null,
    is_stale: false,
    executable_found: true,
  },
  {
    provider: 'codex',
    profile_id: 'codex-default',
    profile_key: 'codex:default',
    label: 'default',
    friendly_name: null,
    sanitized_source: '~/.codex',
    discovery_source: 'default home',
    is_active: true,
    is_authenticated: true,
    last_refresh_utc: '2026-07-26T21:05:00Z',
    last_success_utc: '2026-07-26T21:05:00Z',
    last_error: null,
    is_stale: false,
    executable_found: true,
  },
]

const summary: Summary = {
  total_profiles: 3,
  queried_successfully: 3,
  need_auth: 0,
  over_80_percent: 0,
  over_95_percent: 0,
  next_reset_utc: null,
  stale_or_failed: 0,
  generated_at_utc: '2026-07-26T22:00:00Z',
}

const settings = (autoRefresh: boolean): Settings => ({
  auto_refresh_enabled: autoRefresh,
  refresh_interval_seconds: 60,
  history_retention_days: 90,
  theme: 'system',
  display_timezone: 'Asia/Dhaka',
  hide_sensitive_paths: true,
  notifications_enabled: false,
  notify_at_80_percent: true,
  notify_at_95_percent: true,
  notify_on_exhaustion: true,
  notify_on_auth_required: true,
  notify_on_repeated_failures: true,
  notify_on_reset: true,
  profile_overrides: [],
})

async function renderApp(autoRefresh = true, summaryOverride: Partial<Summary> = {}) {
  vi.resetModules()
  const refreshAll = vi.fn().mockResolvedValue({ profiles_refreshed: 3, results: {} })
  const mockedSummary = { ...summary, ...summaryOverride }
  const usageReport = vi.fn().mockResolvedValue({
    generated_at_utc: '2026-07-26T22:05:00Z',
    profiles_checked: 1,
    rows: [
      {
        profile_key: 'claude:default',
        provider: 'claude',
        label: 'default',
        ok: false,
        source: 'claude /usage live command + statusline fallback',
        message: 'Claude `/usage` ran, but output did not include parseable 5-hour/7-day percentages.',
        limits: [],
      },
    ],
  })
  vi.doMock('./api/client', () => ({
    api: {
      profiles: vi.fn().mockResolvedValue(profiles),
      summary: vi.fn().mockResolvedValue(mockedSummary),
      getSettings: vi.fn().mockResolvedValue(settings(autoRefresh)),
      refreshAll,
      usageReport,
      refreshProfile: vi.fn().mockResolvedValue({ profile_key: 'codex:default', limits: [] }),
      profileLimits: vi.fn().mockResolvedValue([]),
      history: vi.fn().mockResolvedValue([]),
      patchSettings: vi.fn().mockResolvedValue(settings(autoRefresh)),
      diagnostics: vi.fn(),
      deleteHistory: vi.fn(),
    },
  }))
  const { default: App } = await import('./App')
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  )
  return { refreshAll }
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('App refresh orchestration', () => {
  it('triggers one refresh-all after profiles and settings load', async () => {
    const { refreshAll } = await renderApp(true)

    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(1))
  })

  it('does not interval-refresh when auto-refresh is disabled', async () => {
    const { refreshAll } = await renderApp(false)
    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(1))

    vi.advanceTimersByTime(120_000)

    expect(refreshAll).toHaveBeenCalledTimes(1)
  })

  it('interval-refreshes when auto-refresh is enabled', async () => {
    const { refreshAll } = await renderApp(true)
    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(1))

    vi.advanceTimersByTime(60_000)

    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(2))
  })

  it('refreshes shortly after the next reset time passes', async () => {
    vi.setSystemTime(new Date('2026-07-26T21:59:50Z'))
    const { refreshAll } = await renderApp(true, {
      next_reset_utc: '2026-07-26T22:00:00Z',
    })
    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(1))

    vi.advanceTimersByTime(15_000)

    await waitFor(() => expect(refreshAll).toHaveBeenCalledTimes(2))
  })

  it('shows latest real profile refresh time, not summary generation time', async () => {
    await renderApp(true)

    expect(await screen.findByText('Last refresh: 2026-07-26T21:05:00Z')).toBeInTheDocument()
    expect(screen.queryByText('Last refresh: 2026-07-26T22:00:00Z')).not.toBeInTheDocument()
  })

  it('puts Claude default first and Codex default second', async () => {
    await renderApp(true)

    const cards = await screen.findAllByTestId('profile-card')

    expect(cards.map((card) => card.dataset.profileKey).slice(0, 2)).toEqual([
      'claude:default',
      'codex:default',
    ])
  })

  it('runs and displays a usage report', async () => {
    await renderApp(true)

    fireEvent.click(await screen.findByTestId('usage-report-button'))

    expect(await screen.findByText('Usage Report')).toBeInTheDocument()
    expect(screen.getByText('claude /usage live command + statusline fallback')).toBeInTheDocument()
    expect(screen.getByText(/did not include parseable/)).toBeInTheDocument()
  })
})
