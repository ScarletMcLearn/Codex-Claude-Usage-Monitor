import { useState } from 'react'
import clsx from 'clsx'
import type { ProfileStatus, UsageLimit } from '../../types/usage'
import { UsageBar } from './UsageBar'
import { StatusBadge } from '../common/StatusBadge'
import { CountdownTimer } from '../common/CountdownTimer'

export function ProfileCard({
  profile,
  limits,
  displayTimeZone,
  onRefresh,
  onOpenDiagnostics,
  isRefreshing,
}: {
  profile: ProfileStatus
  limits: UsageLimit[]
  displayTimeZone: string
  onRefresh: (profileKey: string) => void
  onOpenDiagnostics: (profileKey: string) => void
  isRefreshing?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const displayName = profile.friendly_name || profile.label
  const providerAccent =
    profile.provider === 'claude'
      ? 'border-l-4 border-l-orange-500'
      : 'border-l-4 border-l-teal-500'

  return (
    <div
      className={clsx(
        'rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 space-y-3',
        providerAccent
      )}
      data-testid="profile-card"
      data-profile-key={profile.profile_key}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={clsx(
                'text-xs font-semibold uppercase tracking-wide',
                profile.provider === 'claude'
                  ? 'text-orange-600 dark:text-orange-400'
                  : 'text-teal-600 dark:text-teal-400'
              )}
            >
              {profile.provider}
            </span>
            {profile.is_stale && <StatusBadge quality="stale" />}
          </div>
          <h3 className="font-semibold text-slate-900 dark:text-slate-50">{displayName}</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400" title={profile.sanitized_source}>
            {profile.sanitized_source}
          </p>
        </div>
        <button
          type="button"
          className="shrink-0 rounded-md border border-slate-300 dark:border-slate-600 px-2 py-1 text-xs font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
          onClick={() => onRefresh(profile.profile_key)}
          disabled={isRefreshing}
          aria-label={`Refresh ${displayName}`}
        >
          {isRefreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {profile.last_error && (
        <p className="text-xs text-red-600 dark:text-red-400">{profile.last_error}</p>
      )}

      <div className="space-y-3">
        {limits.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No usage data yet.</p>
        ) : (
          limits.map((limit) => (
            <div key={limit.window_id} className="space-y-1">
              <UsageBar
                usedPercent={limit.used_percent}
                quality={limit.quality}
                unavailableReason={limit.unavailable_reason}
                label={limit.window_label}
              />
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Resets: <CountdownTimer targetIso={limit.resets_at_utc} displayTimeZone={displayTimeZone} /></span>
                <StatusBadge quality={limit.quality} />
              </div>
            </div>
          ))
        )}
      </div>

      <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-100 dark:border-slate-700">
        <button
          type="button"
          className="text-slate-600 dark:text-slate-300 underline underline-offset-2"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? 'Hide details' : 'Show details'}
        </button>
        <button
          type="button"
          className="text-slate-600 dark:text-slate-300 underline underline-offset-2"
          onClick={() => onOpenDiagnostics(profile.profile_key)}
        >
          Diagnostics
        </button>
      </div>

      {expanded && (
        <div className="rounded-md bg-slate-50 dark:bg-slate-900/40 p-2 text-xs text-slate-600 dark:text-slate-300 space-y-1">
          <p>Discovery source: {profile.discovery_source}</p>
          <p>Last refresh: {profile.last_refresh_utc ?? 'never'}</p>
          <p>Last success: {profile.last_success_utc ?? 'never'}</p>
        </div>
      )}
    </div>
  )
}
