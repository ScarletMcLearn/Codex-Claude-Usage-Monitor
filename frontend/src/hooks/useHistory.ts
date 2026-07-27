import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { HistoryRange } from '../types/usage'

export function useHistory(params: {
  provider?: string
  profile_key?: string
  window_id?: string
  range: HistoryRange
}) {
  return useQuery({
    queryKey: ['history', params],
    queryFn: () => api.history(params),
    refetchInterval: 15_000,
  })
}
