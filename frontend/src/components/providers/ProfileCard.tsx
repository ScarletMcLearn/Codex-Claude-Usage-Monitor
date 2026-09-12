import { useState, type ReactNode } from 'react'
import clsx from 'clsx'
import type { ProfileStatus, UsageLimit } from '../../types/usage'
import { UsageBar } from './UsageBar'
import { StatusBadge } from '../common/StatusBadge'
import { CountdownTimer } from '../common/CountdownTimer'

function formatPercent(value: number | null) {
  return value === null ? '—' : `${value.toFixed(0)}%`
}

function formatUsed(limit: UsageLimit) {
  if (limit.used_percent !== null) return formatPercent(limit.used_percent)
  if (limit.used_units !== null) return `${limit.used_units.toFixed(0)} req`
  return '—'
}

function freeAIQuotaLabel(limit: UsageLimit) {
  if (limit.quality === 'unavailable') return 'No local logs'
  if (limit.max_units !== null) return `${limit.max_units.toFixed(0)} max`
  return 'Not probed'
}

function sourceLabel(limit: UsageLimit) {
  const source = limit.source_detail.source
  if (source === 'free_ai_local_router_logs') return 'Local logs'
  if (source === 'free_ai_local_files') return 'Local files'
  return 'Provider'
}

function providerLabel(provider: ProfileStatus['provider']) {
  if (provider === 'free_ai') return 'Free-AI'
  return provider
}

function Metric({
  label,
  value,
  className,
  valueClassName,
  testId,
}: {
  label: string
  value: ReactNode
  className?: string
  valueClassName?: string
  testId?: string
}) {
  return (
    <div
      className={clsx(
        'min-w-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900/40',
        className
      )}
    >
      <p className="text-[11px] font-semibold uppercase text-slate-500 dark:text-slate-400">{label}</p>
      <p
        className={clsx(
          'text-xl font-semibold leading-tight text-slate-900 dark:text-slate-50',
          valueClassName
        )}
        data-testid={testId}
      >
        {value}
      </p>
    </div>
  )
}

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
  const isFreeAI = profile.provider === 'free_ai'
  const providerAccent =
    profile.provider === 'claude'
      ? 'border-l-4 border-l-orange-500'
      : profile.provider === 'codex'
        ? 'border-l-4 border-l-teal-500'
        : profile.provider === 'free_ai'
          ? 'border-l-4 border-l-emerald-500'
          : 'border-l-4 border-l-blue-500'
  const providerText =
    profile.provider === 'claude'
      ? 'text-orange-600 dark:text-orange-400'
      : profile.provider === 'codex'
        ? 'text-teal-600 dark:text-teal-400'
        : profile.provider === 'free_ai'
          ? 'text-emerald-600 dark:text-emerald-400'
          : 'text-blue-600 dark:text-blue-400'

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
                providerText
              )}
            >
              {providerLabel(profile.provider)}
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
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No usage snapshots captured yet. Refresh this profile to query provider usage.
          </p>
        ) : (
          limits.map((limit) => (
            <div
              key={limit.window_id}
              className="space-y-2 rounded-md border border-slate-100 p-2 dark:border-slate-700/70"
            >
              {isFreeAI ? (
                <div className="grid grid-cols-2 gap-2">
                  <Metric label="Requests" value={formatUsed(limit)} testId="used-percent" />
                  <Metric
                    label="Quota"
                    value={freeAIQuotaLabel(limit)}
                    valueClassName="text-base text-slate-700 dark:text-slate-200"
                    testId="remaining-percent"
                  />
                  <Metric
                    label="Source"
                    value={sourceLabel(limit)}
                    className="col-span-2"
                    valueClassName="text-base text-slate-700 dark:text-slate-200"
                    testId="reset-countdown"
                  />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <Metric label="Used" value={formatUsed(limit)} testId="used-percent" />
                    <Metric
                      label="Remaining"
                      value={formatPercent(limit.remaining_percent)}
                      valueClassName="text-emerald-700 dark:text-emerald-300"
                      testId="remaining-percent"
                    />
                    <Metric
                      label="Reset"
                      value={
                        <CountdownTimer
                          targetIso={limit.resets_at_utc}
                          displayTimeZone={displayTimeZone}
                          isStale={limit.quality === 'stale'}
                          showLocalTime={false}
                        />
                      }
                      className="col-span-2"
                      valueClassName="whitespace-normal text-2xl"
                      testId="reset-countdown"
                    />
                  </div>
                  <UsageBar
                    usedPercent={limit.used_percent}
                    quality={limit.quality}
                    unavailableReason={limit.unavailable_reason}
                    label={limit.window_label}
                  />
                </>
              )}
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Status</span>
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
