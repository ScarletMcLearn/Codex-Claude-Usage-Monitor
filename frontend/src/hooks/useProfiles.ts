import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useProfiles() {
  return useQuery({
    queryKey: ['profiles'],
    queryFn: api.profiles,
    refetchInterval: 15_000,
  })
}
