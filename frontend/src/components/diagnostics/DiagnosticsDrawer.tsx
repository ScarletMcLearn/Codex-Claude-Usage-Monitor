import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { ProfileDiagnostics } from '../../types/usage'

export function DiagnosticsDrawer({
  profileKey,
  onClose,
}: {
  profileKey: string | null
  onClose: () => void
}) {
  const [diag, setDiag] = useState<ProfileDiagnostics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!profileKey) return
    setLoading(true)
    setError(null)
    api
      .diagnostics(profileKey)
      .then(setDiag)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [profileKey])

  if (!profileKey) return null

  return (
    <div
      className="fixed inset-0 z-20 flex justify-end bg-black/30"
      role="dialog"
      aria-modal="true"
      aria-label="Diagnostics"
      onClick={onClose}
    >
      <div
        className="h-full w-full max-w-md bg-white dark:bg-slate-900 shadow-xl p-4 overflow-y-auto space-y-3"
        onClick={(e) => e.stopPropagation()}
        data-testid="diagnostics-drawer"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Diagnostics</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Close diagnostics"
          >
            ✕
          </button>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading…</p>}
        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        {diag && (
          <dl className="space-y-2 text-sm">
            <Row label="Provider" value={diag.provider} />
            <Row label="Discovery source" value={diag.discovery_source} />
            <Row label="Config path" value={diag.sanitized_config_path} />
            <Row label="Parser used" value={diag.parser_used ?? 'n/a'} />
            <Row label="Last command result" value={diag.last_command_result ?? 'n/a'} />
            <Row
              label="Last successful query"
              value={diag.last_successful_query_utc ?? 'never'}
            />
            <Row label="Current error" value={diag.current_error ?? 'none'} />
            <Row label="Suggested action" value={diag.suggested_action ?? 'none'} />
            {diag.notifier_db_available !== null && diag.notifier_db_available !== undefined && (
              <Row
                label="Notifier DB available"
                value={diag.notifier_db_available ? 'yes' : `no (${diag.notifier_db_reason ?? 'unknown reason'})`}
              />
            )}
          </dl>
        )}
        <p className="text-xs text-slate-400 dark:text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-800">
          Diagnostics are sanitized: no secrets, tokens, or full file contents are ever shown.
        </p>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">{label}</dt>
      <dd className="text-slate-800 dark:text-slate-100 break-words">{value}</dd>
    </div>
  )
}
