import type {
  HistoryRange,
  HistoryRow,
  ProfileDiagnostics,
  ProfileStatus,
  Settings,
  Summary,
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
}

export { ApiError }
