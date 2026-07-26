import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function useRefreshAll() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.refreshAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export function useRefreshProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (profileKey: string) => api.refreshProfile(profileKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export function useSettingsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.patchSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}
