import { useMemo, useState } from 'react'
import type { HistoryRange, ProfileStatus } from '../../types/usage'
import { useHistory } from '../../hooks/useHistory'
import { HistoryFilters } from './HistoryFilters'
import { HistoryChart } from './HistoryChart'
import { api } from '../../api/client'
import { useQueryClient } from '@tanstack/react-query'

export function HistoryPanel({ profiles }: { profiles: ProfileStatus[] }) {
  const [profileKey, setProfileKey] = useState<string | null>(null)
  const [windowId, setWindowId] = useState<string | null>(null)
  const [range, setRange] = useState<HistoryRange>('7d')
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const queryClient = useQueryClient()

  const { data: rows, isLoading } = useHistory({
    profile_key: profileKey ?? undefined,
    window_id: windowId ?? undefined,
    range,
  })

  const windowOptions = useMemo(() => {
    const set = new Set<string>()
    for (const row of rows ?? []) set.add(row.window_id)
    return Array.from(set).sort()
  }, [rows])

  async function handleDelete() {
    if (!confirmingDelete) {
      setConfirmingDelete(true)
      return
    }
    await api.deleteHistory(true)
    setConfirmingDelete(false)
    queryClient.invalidateQueries({ queryKey: ['history'] })
  }

  return (
    <section className="space-y-3" aria-labelledby="history-heading">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 id="history-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-50">
          History
        </h2>
        <div className="flex items-center gap-2">
          {confirmingDelete && (
            <span className="text-xs text-red-600 dark:text-red-400">
              Click again to permanently delete all history.
            </span>
          )}
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md border border-red-300 dark:border-red-700 text-red-700 dark:text-red-400 px-2 py-1 text-xs font-medium hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            {confirmingDelete ? 'Confirm delete all history' : 'Delete all history'}
          </button>
        </div>
      </div>

      <HistoryFilters
        profiles={profiles}
        selectedProfileKey={profileKey}
        onSelectProfile={setProfileKey}
        selectedWindowId={windowId}
        onSelectWindow={setWindowId}
        windowOptions={windowOptions}
        range={range}
        onSelectRange={setRange}
      />

      {isLoading ? (
        <div className="h-80 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      ) : (
        <HistoryChart rows={rows ?? []} />
      )}
    </section>
  )
}
