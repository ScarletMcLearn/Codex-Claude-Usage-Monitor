import { useMemo, useState } from 'react'
import { useProfiles } from './hooks/useProfiles'
import { useSummary } from './hooks/useSummary'
import { useSettings } from './hooks/useSettings'
import { useRefreshAll, useRefreshProfile, useSettingsMutation } from './hooks/useRefresh'
import { api } from './api/client'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Header } from './components/layout/Header'
import { SummaryCards } from './components/layout/SummaryCards'
import { ProviderSection } from './components/providers/ProviderSection'
import { HistoryPanel } from './components/history/HistoryPanel'
import { DiagnosticsDrawer } from './components/diagnostics/DiagnosticsDrawer'
import { SkeletonCard } from './components/common/SkeletonCard'
import { EmptyState } from './components/common/EmptyState'
import type { UsageLimit } from './types/usage'

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

export default function App() {
  const { data: profiles, isLoading: profilesLoading } = useProfiles()
  const { data: summary } = useSummary()
  const { data: settings } = useSettings()
  const settingsMutation = useSettingsMutation()
  const refreshAll = useRefreshAll()
  const refreshProfile = useRefreshProfile()
  const queryClient = useQueryClient()

  const [diagnosticsProfileKey, setDiagnosticsProfileKey] = useState<string | null>(null)
  const [refreshingKey, setRefreshingKey] = useState<string | null>(null)

  const profileKeys = useMemo(() => (profiles ?? []).map((p) => p.profile_key), [profiles])
  const { data: limitsByProfile } = useAllLimits(profileKeys)

  const claudeProfiles = (profiles ?? []).filter((p) => p.provider === 'claude')
  const codexProfiles = (profiles ?? []).filter((p) => p.provider === 'codex')

  const displayTimeZone = settings?.display_timezone ?? 'Asia/Dhaka'

  const health = useMemo<'good' | 'warning' | 'critical' | 'unknown'>(() => {
    if (!summary) return 'unknown'
    if (summary.over_95_percent > 0 || summary.need_auth > 0) return 'critical'
    if (summary.over_80_percent > 0 || summary.stale_or_failed > 0) return 'warning'
    return 'good'
  }, [summary])

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
        lastRefresh={summary?.generated_at_utc ?? null}
        onRefreshAll={handleRefreshAll}
        refreshing={refreshAll.isPending}
        autoRefreshEnabled={settings?.auto_refresh_enabled ?? true}
        onToggleAutoRefresh={(v) => settingsMutation.mutate({ auto_refresh_enabled: v })}
        refreshIntervalSeconds={settings?.refresh_interval_seconds ?? 300}
        onChangeInterval={(v) => settingsMutation.mutate({ refresh_interval_seconds: v })}
        theme={settings?.theme ?? 'system'}
        onChangeTheme={(v) => settingsMutation.mutate({ theme: v })}
        health={health}
      />

      <main className="mx-auto max-w-7xl p-4 space-y-8">
        {summary && <SummaryCards summary={summary} displayTimeZone={displayTimeZone} />}

        {(profiles ?? []).length === 0 ? (
          <EmptyState
            title="No profiles discovered yet"
            description="Click Refresh all, or check that Claude Code / Codex CLI are installed on this machine."
          />
        ) : (
          <>
            <ProviderSection
              provider="claude"
              title="Claude Code"
              profiles={claudeProfiles}
              limitsByProfile={limitsByProfile ?? {}}
              displayTimeZone={displayTimeZone}
              onRefresh={handleRefreshProfile}
              onOpenDiagnostics={setDiagnosticsProfileKey}
              refreshingKey={refreshingKey}
            />
            <ProviderSection
              provider="codex"
              title="Codex"
              profiles={codexProfiles}
              limitsByProfile={limitsByProfile ?? {}}
              displayTimeZone={displayTimeZone}
              onRefresh={handleRefreshProfile}
              onOpenDiagnostics={setDiagnosticsProfileKey}
              refreshingKey={refreshingKey}
            />
          </>
        )}

        <HistoryPanel profiles={profiles ?? []} />
      </main>

      <DiagnosticsDrawer profileKey={diagnosticsProfileKey} onClose={() => setDiagnosticsProfileKey(null)} />
    </div>
  )
}
