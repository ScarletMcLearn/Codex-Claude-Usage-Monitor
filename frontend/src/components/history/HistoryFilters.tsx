import type { HistoryRange, ProfileStatus } from '../../types/usage'

const RANGES: { key: HistoryRange; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: 'all', label: 'All' },
]

export function HistoryFilters({
  profiles,
  selectedProfileKey,
  onSelectProfile,
  selectedWindowId,
  onSelectWindow,
  windowOptions,
  range,
  onSelectRange,
}: {
  profiles: ProfileStatus[]
  selectedProfileKey: string | null
  onSelectProfile: (key: string | null) => void
  selectedWindowId: string | null
  onSelectWindow: (id: string | null) => void
  windowOptions: string[]
  range: HistoryRange
  onSelectRange: (r: HistoryRange) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3" data-testid="history-filters">
      <label className="flex items-center gap-1 text-sm">
        Profile
        <select
          className="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1"
          value={selectedProfileKey ?? ''}
          onChange={(e) => onSelectProfile(e.target.value || null)}
        >
          <option value="">All profiles</option>
          {profiles.map((p) => (
            <option key={p.profile_key} value={p.profile_key}>
              {p.friendly_name || p.label} ({p.provider})
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1 text-sm">
        Limit
        <select
          className="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1"
          value={selectedWindowId ?? ''}
          onChange={(e) => onSelectWindow(e.target.value || null)}
        >
          <option value="">All limits</option>
          {windowOptions.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-center gap-1" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r.key}
            type="button"
            onClick={() => onSelectRange(r.key)}
            aria-pressed={range === r.key}
            className={`rounded-md px-2 py-1 text-sm ${
              range === r.key
                ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                : 'border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200'
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>
    </div>
  )
}
