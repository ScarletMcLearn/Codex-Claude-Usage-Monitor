import { ThemeToggle } from '../common/ThemeToggle'

type HealthLevel = 'good' | 'warning' | 'critical' | 'unknown'

const HEALTH_META: Record<HealthLevel, { label: string; icon: string; color: string }> = {
  good: { label: 'All good', icon: '✓', color: 'text-emerald-600 dark:text-emerald-400' },
  warning: { label: 'Needs attention', icon: '⚠', color: 'text-amber-600 dark:text-amber-400' },
  critical: { label: 'Critical', icon: '⛔', color: 'text-red-600 dark:text-red-400' },
  unknown: { label: 'Unknown', icon: '?', color: 'text-slate-500 dark:text-slate-400' },
}

export function Header({
  lastRefresh,
  onRefreshAll,
  refreshing,
  onUsageReport,
  reporting,
  autoRefreshEnabled,
  onToggleAutoRefresh,
  refreshIntervalSeconds,
  onChangeInterval,
  theme,
  onChangeTheme,
  health,
}: {
  lastRefresh: string | null
  onRefreshAll: () => void
  refreshing: boolean
  onUsageReport: () => void
  reporting: boolean
  autoRefreshEnabled: boolean
  onToggleAutoRefresh: (v: boolean) => void
  refreshIntervalSeconds: number
  onChangeInterval: (v: number) => void
  theme: 'light' | 'dark' | 'system'
  onChangeTheme: (v: 'light' | 'dark' | 'system') => void
  health: HealthLevel
}) {
  const meta = HEALTH_META[health]
  return (
    <header className="border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto max-w-7xl px-4 py-3 flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-50">
            Claude &amp; Codex Usage Monitor
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Last refresh: {lastRefresh ?? 'never'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className={`flex items-center gap-1 text-sm font-medium ${meta.color}`} data-testid="health-indicator">
            <span aria-hidden="true">{meta.icon}</span>
            {meta.label}
          </span>

          <label className="flex items-center gap-1 text-sm text-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              checked={autoRefreshEnabled}
              onChange={(e) => onToggleAutoRefresh(e.target.checked)}
            />
            Auto-refresh
          </label>

          <label className="flex items-center gap-1 text-sm text-slate-700 dark:text-slate-200">
            every
            <select
              className="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-1 py-0.5"
              value={refreshIntervalSeconds}
              onChange={(e) => onChangeInterval(Number(e.target.value))}
              aria-label="Auto-refresh interval"
            >
              <option value={60}>1m</option>
              <option value={300}>5m</option>
              <option value={600}>10m</option>
              <option value={1800}>30m</option>
            </select>
          </label>

          <button
            type="button"
            data-testid="refresh-all-button"
            onClick={onRefreshAll}
            disabled={refreshing}
            className="rounded-md bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {refreshing ? 'Refreshing…' : 'Refresh all'}
          </button>

          <button
            type="button"
            data-testid="usage-report-button"
            onClick={onUsageReport}
            disabled={reporting}
            className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            {reporting ? 'Checking…' : 'Usage report'}
          </button>

          <ThemeToggle value={theme} onChange={onChangeTheme} />
        </div>
      </div>
    </header>
  )
}
