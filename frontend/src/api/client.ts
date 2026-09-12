import type {
  HistoryRange,
  HistoryRow,
  ProfileDiagnostics,
  ProfileStatus,
  Settings,
  Summary,
  UsageReport,
  ForensicOverview,
  ForensicHotspots,
  PaginatedForensicSessions,
  ForensicSessionDetail,
  ForensicTurnDetail,
  UsageLimit,
} from '../types/usage'

const BASE = '/api'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string; time_utc: string }>('/health'),
  providers: () => request<Array<{ provider: string; display_name: string }>>('/providers'),
  profiles: () => request<ProfileStatus[]>('/profiles'),
  refreshDiscovery: () => request<{ discovered: number }>('/discovery/refresh', { method: 'POST' }),
  refreshProfile: (profileKey: string) =>
    request<{ profile_key: string; limits: UsageLimit[] }>(
      `/profiles/${encodeURIComponent(profileKey)}/refresh`,
      { method: 'POST' }
    ),
  refreshAll: () =>
    request<{ profiles_refreshed: number; results: Record<string, UsageLimit[]> }>(
      '/refresh-all',
      { method: 'POST' }
    ),
  usageReport: () => request<UsageReport>('/usage-report', { method: 'POST' }),
  profileLimits: (profileKey: string) =>
    request<UsageLimit[]>(`/profiles/${encodeURIComponent(profileKey)}/limits`),
  history: (params: {
    provider?: string
    profile_key?: string
    window_id?: string
    range?: HistoryRange
  }) => {
    const query = new URLSearchParams()
    if (params.provider) query.set('provider', params.provider)
    if (params.profile_key) query.set('profile_key', params.profile_key)
    if (params.window_id) query.set('window_id', params.window_id)
    query.set('range', params.range ?? '7d')
    return request<HistoryRow[]>(`/history?${query.toString()}`)
  },
  deleteHistory: (confirm: boolean) =>
    request<{ deleted: number }>(`/history?confirm=${confirm}`, { method: 'DELETE' }),
  summary: () => request<Summary>('/summary'),
  getSettings: () => request<Settings>('/settings'),
  patchSettings: (patch: Partial<Settings>) =>
    request<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(patch) }),
  diagnostics: (profileKey: string) =>
    request<ProfileDiagnostics>(`/diagnostics/${encodeURIComponent(profileKey)}`),
  forensicOverview: () => request<ForensicOverview>('/forensics/overview'),
  forensicRefresh: () => request<{
    sources_scanned: number
    events_processed: number
    events_skipped: number
    malformed_events: number
    model_generation_requests: number
  }>('/forensics/refresh', { method: 'POST' }),
  forensicSessions: (params?: {
    offset?: number
    agent?: string
    token_quality?: string
    min_total_tokens?: number
    has_tools?: boolean
    has_commands?: boolean
    has_child_relationships?: boolean
  }) => {
    const query = new URLSearchParams()
    query.set('limit', '50')
    query.set('offset', String(params?.offset ?? 0))
    if (params?.agent) query.set('agent', params.agent)
    if (params?.token_quality) query.set('token_quality', params.token_quality)
    if (params?.min_total_tokens != null) query.set('min_total_tokens', String(params.min_total_tokens))
    if (params?.has_tools) query.set('has_tools', 'true')
    if (params?.has_commands) query.set('has_commands', 'true')
    if (params?.has_child_relationships) query.set('has_child_relationships', 'true')
    return request<PaginatedForensicSessions>(`/forensics/sessions?${query.toString()}`)
  },
  forensicSession: (sessionId: string) =>
    request<ForensicSessionDetail>(`/forensics/sessions/${encodeURIComponent(sessionId)}`),
  forensicTurn: (turnId: string) =>
    request<ForensicTurnDetail>(`/forensics/turns/${encodeURIComponent(turnId)}`),
  forensicHotspots: () => request<ForensicHotspots>('/forensics/hotspots'),
  forensicExport: (exportType: 'summary' | 'full', warningAck = false) =>
    request<{ path: string; export_type: string; created_at_utc: string }>(
      `/forensics/export?export_type=${exportType}&warning_ack=${warningAck}`,
      { method: 'POST' }
    ),
}

export { ApiError }
