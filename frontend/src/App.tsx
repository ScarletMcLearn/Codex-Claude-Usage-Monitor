import { useEffect, useMemo, useRef, useState } from 'react'
import { useProfiles } from './hooks/useProfiles'
import { useSummary } from './hooks/useSummary'
import { useSettings } from './hooks/useSettings'
import { useRefreshAll, useRefreshProfile, useSettingsMutation } from './hooks/useRefresh'
import { api } from './api/client'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Header } from './components/layout/Header'
import { SummaryCards } from './components/layout/SummaryCards'
import { UsageReportPanel } from './components/layout/UsageReportPanel'
import { ProfileCard } from './components/providers/ProfileCard'
import { HistoryPanel } from './components/history/HistoryPanel'
import { DiagnosticsDrawer } from './components/diagnostics/DiagnosticsDrawer'
import { SkeletonCard } from './components/common/SkeletonCard'
import { EmptyState } from './components/common/EmptyState'
import type { ProfileStatus, UsageLimit, UsageReport } from './types/usage'

let initialRefreshStartedForSession = false
const RESET_REFRESH_BUFFER_MS = 5_000
const RESET_REFRESH_RETRY_MS = 30_000

function useAllLimits(profileKeys: string[]) {
  const queries = profileKeys.map((key) => ({
    queryKey: ['limits', key],
    queryFn: () => api.profileLimits(key),
  }))
  // Simple sequential fan-out via a single aggregate query keeps this app
  // free of extra deps (no react-query useQueries needed for this scale).
  return useQuery({
    queryKey: ['limits-all', profileKeys],
    queryFn: async () => {
      const entries = await Promise.all(
        queries.map(async (q) => [q.queryKey[1] as string, await q.queryFn()] as const)
      )
      return Object.fromEntries(entries) as Record<string, UsageLimit[]>
    },
    enabled: profileKeys.length > 0,
    refetchInterval: 15_000,
  })
}

function isDefaultProfile(profile: ProfileStatus) {
  return profile.label.toLowerCase() === 'default' || profile.profile_id.toLowerCase() === 'default'
}

function cardOrder(profile: ProfileStatus) {
  if (profile.provider === 'claude' && isDefaultProfile(profile)) return 0
  if (profile.provider === 'codex' && isDefaultProfile(profile)) return 1
  if (profile.provider === 'antigravity' && isDefaultProfile(profile)) return 2
  if (profile.provider === 'free_ai') return 3
  if (isDefaultProfile(profile)) return 3
  if (profile.provider === 'claude') return 4
  if (profile.provider === 'codex') return 5
  return 6
}

export default function App() {
  const {
    data: profiles,
    isLoading: profilesLoading,
    isError: profilesError,
  } = useProfiles()
  const { data: summary, isError: summaryError } = useSummary()
  const { data: settings, isLoading: settingsLoading, isError: settingsError } = useSettings()
  const settingsMutation = useSettingsMutation()
  const refreshAll = useRefreshAll()
  const refreshProfile = useRefreshProfile()
  const queryClient = useQueryClient()

  const [diagnosticsProfileKey, setDiagnosticsProfileKey] = useState<string | null>(null)
  const [refreshingKey, setRefreshingKey] = useState<string | null>(null)
  const [usageReport, setUsageReport] = useState<UsageReport | null>(null)
  const [usageReportError, setUsageReportError] = useState<string | null>(null)
  const [usageReportLoading, setUsageReportLoading] = useState(false)

  const profileKeys = useMemo(() => (profiles ?? []).map((p) => p.profile_key), [profiles])
  const { data: limitsByProfile, isError: limitsError } = useAllLimits(profileKeys)

  const orderedProfiles = useMemo(
    () =>
      [...(profiles ?? [])].sort((a, b) => {
        const orderDelta = cardOrder(a) - cardOrder(b)
        if (orderDelta !== 0) return orderDelta
        return (a.friendly_name || a.label).localeCompare(b.friendly_name || b.label)
      }),
    [profiles]
  )

  const displayTimeZone = settings?.display_timezone ?? 'Asia/Dhaka'
  const latestRefresh = useMemo(() => {
    const timestamps = (profiles ?? [])
      .map((profile) => profile.last_refresh_utc ?? profile.last_success_utc)
      .filter((value): value is string => Boolean(value))
    if (timestamps.length === 0) return null
    return timestamps.reduce((latest, value) =>
      Date.parse(value) > Date.parse(latest) ? value : latest
    )
  }, [profiles])
  const dataStale = useMemo(() => {
    if (!settings?.auto_refresh_enabled) return false
    if ((profiles ?? []).length === 0) return false
    if (!latestRefresh) return true
    const latestMs = Date.parse(latestRefresh)
    if (!Number.isFinite(latestMs)) return true
    const staleAfterMs = Math.max(5 * 60_000, (settings.refresh_interval_seconds ?? 300) * 1_000 * 2)
    return Date.now() - latestMs > staleAfterMs
  }, [latestRefresh, profiles, settings?.auto_refresh_enabled, settings?.refresh_interval_seconds])

  const health = useMemo<'good' | 'warning' | 'critical' | 'unknown'>(() => {
    if (profilesError || summaryError || settingsError || limitsError) return 'critical'
    if (dataStale) return 'warning'
    if (!summary) return 'unknown'
    if (summary.over_95_percent > 0 || summary.need_auth > 0) return 'critical'
    if (summary.over_80_percent > 0 || summary.stale_or_failed > 0) return 'warning'
    return 'good'
  }, [dataStale, limitsError, profilesError, settingsError, summary, summaryError])

  async function handleRefreshProfile(profileKey: string) {
    setRefreshingKey(profileKey)
    try {
      await refreshProfile.mutateAsync(profileKey)
      queryClient.invalidateQueries({ queryKey: ['limits-all'] })
    } finally {
      setRefreshingKey(null)
    }
  }

  async function handleRefreshAll() {
    await refreshAll.mutateAsync()
    queryClient.invalidateQueries({ queryKey: ['limits-all'] })
  }

  async function handleUsageReport() {
    setUsageReportLoading(true)
    setUsageReportError(null)
    try {
      setUsageReport(await api.usageReport())
    } catch (error) {
      setUsageReportError(error instanceof Error ? error.message : 'Usage report failed')
    } finally {
      setUsageReportLoading(false)
    }
  }

  const initialRefreshStarted = useRef(false)
  const resetRefreshAttempts = useRef(new Map<string, number>())
  const [resetRefreshTick, setResetRefreshTick] = useState(0)
  useEffect(() => {
    if (
      profilesLoading ||
      settingsLoading ||
      initialRefreshStarted.current ||
      initialRefreshStartedForSession
    ) {
      return
    }
    initialRefreshStarted.current = true
    initialRefreshStartedForSession = true
    void handleRefreshAll()
    // Run once after initial profile/settings load; interval handles later refreshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profilesLoading, settingsLoading])

  useEffect(() => {
    if (!settings?.auto_refresh_enabled) return
    const intervalSeconds = Math.max(30, settings.refresh_interval_seconds)
    const intervalId = window.setInterval(() => {
      void handleRefreshAll()
    }, intervalSeconds * 1000)
    return () => window.clearInterval(intervalId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings?.auto_refresh_enabled, settings?.refresh_interval_seconds])

  const resetRefreshCandidates = useMemo(() => {
    const resetTimes = [
      summary?.next_reset_utc,
      ...Object.values(limitsByProfile ?? {})
        .flat()
        .map((limit) => limit.resets_at_utc),
    ]
      .filter((value): value is string => Boolean(value))
      .map((value) => ({ value, time: Date.parse(value) }))
      .filter((item) => Number.isFinite(item.time))
      .sort((a, b) => a.time - b.time)

    return Array.from(new Map(resetTimes.map((item) => [item.value, item])).values())
  }, [limitsByProfile, summary?.next_reset_utc])

  useEffect(() => {
    if (!settings?.auto_refresh_enabled) return
    const candidateValues = new Set(resetRefreshCandidates.map((item) => item.value))
    for (const value of resetRefreshAttempts.current.keys()) {
      if (!candidateValues.has(value)) resetRefreshAttempts.current.delete(value)
    }

    const now = Date.now()
    const nextResetRefresh = resetRefreshCandidates[0]
    if (!nextResetRefresh) return

    const targetDelay = nextResetRefresh.time + RESET_REFRESH_BUFFER_MS - now
    const lastAttempt = resetRefreshAttempts.current.get(nextResetRefresh.value)
    const retryDelay = lastAttempt === undefined ? 0 : lastAttempt + RESET_REFRESH_RETRY_MS - now
    const delay = Math.max(0, targetDelay, retryDelay)

    const timeoutId = window.setTimeout(() => {
      resetRefreshAttempts.current.set(nextResetRefresh.value, Date.now())
      void handleRefreshAll().finally(() => setResetRefreshTick((tick) => tick + 1))
    }, delay)

    return () => window.clearTimeout(timeoutId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetRefreshCandidates, resetRefreshTick, settings?.auto_refresh_enabled])

  if (profilesLoading) {
    return (
      <div className="mx-auto max-w-7xl p-4 space-y-4">
        <SkeletonCard lines={2} />
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full">
      <Header
        lastRefresh={latestRefresh}
        dataStale={dataStale}
        onRefreshAll={handleRefreshAll}
        refreshing={refreshAll.isPending}
        onUsageReport={handleUsageReport}
        reporting={usageReportLoading}
        autoRefreshEnabled={settings?.auto_refresh_enabled ?? true}
        onToggleAutoRefresh={(v) => settingsMutation.mutate({ auto_refresh_enabled: v })}
        refreshIntervalSeconds={settings?.refresh_interval_seconds ?? 300}
        onChangeInterval={(v) => settingsMutation.mutate({ refresh_interval_seconds: v })}
        theme={settings?.theme ?? 'system'}
        onChangeTheme={(v) => settingsMutation.mutate({ theme: v })}
        health={health}
      />

      <main className="mx-auto max-w-7xl p-4 space-y-8">
        <UsageReportPanel
          report={usageReport}
          error={usageReportError}
          onClose={() => {
            setUsageReport(null)
            setUsageReportError(null)
          }}
        />

        {summary && <SummaryCards summary={summary} displayTimeZone={displayTimeZone} />}

        {(profiles ?? []).length === 0 ? (
          <EmptyState
            title="No profiles discovered yet"
            description="Click Refresh all, or check that Claude Code, Codex CLI, Antigravity, or Free-AI are installed on this machine."
          />
        ) : (
          <section aria-labelledby="section-profiles" className="space-y-3">
            <h2 id="section-profiles" className="text-lg font-semibold text-slate-800 dark:text-slate-100">
              Profiles
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {orderedProfiles.map((profile) => (
                <ProfileCard
                  key={profile.profile_key}
                  profile={profile}
                  limits={limitsByProfile?.[profile.profile_key] ?? []}
                  displayTimeZone={displayTimeZone}
                  onRefresh={handleRefreshProfile}
                  onOpenDiagnostics={setDiagnosticsProfileKey}
                  isRefreshing={refreshingKey === profile.profile_key}
                />
              ))}
            </div>
          </section>
        )}

        <HistoryPanel profiles={profiles ?? []} />
      </main>

      <DiagnosticsDrawer profileKey={diagnosticsProfileKey} onClose={() => setDiagnosticsProfileKey(null)} />
    </div>
  )
}
