import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

function tokenText(value: number | null | undefined) {
  return value == null ? 'Unavailable from source telemetry' : value.toLocaleString()
}

export function ForensicsPanel() {
  const queryClient = useQueryClient()
  const overview = useQuery({ queryKey: ['forensics-overview'], queryFn: api.forensicOverview })
  const sessions = useQuery({ queryKey: ['forensics-sessions'], queryFn: api.forensicSessions })

  async function refresh() {
    await api.forensicRefresh()
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['forensics-overview'] }),
      queryClient.invalidateQueries({ queryKey: ['forensics-sessions'] }),
    ])
  }

  async function exportBundle(exportType: 'summary' | 'full') {
    const warningAck =
      exportType === 'full'
        ? window.confirm('Full forensic exports may contain prompts, source code, command output, and model output. Continue?')
        : false
    if (exportType === 'full' && !warningAck) return
    const result = await api.forensicExport(exportType, warningAck)
    window.alert(`Export created locally:\n${result.path}`)
  }

  const data = overview.data

  return (
    <section aria-labelledby="section-forensics" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="section-forensics" className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            Token Forensics
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Passive local evidence. Monitoring generation requests: {data?.zero_token_counters.monitor_model_generation_requests ?? 0}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900" onClick={refresh}>
            Refresh evidence
          </button>
          <button className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700" onClick={() => exportBundle('summary')}>
            Summary export
          </button>
          <button className="rounded-md border border-amber-400 px-3 py-2 text-sm text-amber-800 dark:text-amber-200" onClick={() => exportBundle('full')}>
            Full forensic export
          </button>
        </div>
      </div>

      {overview.isError ? (
        <p className="text-sm text-red-600">Forensic overview unavailable.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Object.entries(data?.counts ?? {}).slice(0, 8).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
              <div className="text-xs uppercase text-slate-500">{key.replace('forensic_', '')}</div>
              <div className="text-xl font-semibold text-slate-900 dark:text-slate-50">{value.toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Expensive Turns</h3>
          <div className="mt-3 space-y-3">
            {(data?.expensive_turns ?? []).slice(0, 8).map((turn) => (
              <div key={turn.turn_id} className="border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{turn.model ?? turn.event_type ?? 'Unknown model'}</span>
                  <span>{tokenText(turn.total_tokens)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">
                  {turn.user_preview || turn.assistant_preview || 'No local preview exposed'}
                </p>
                <div className="mt-1 text-xs text-slate-500">quality: {turn.token_quality}</div>
              </div>
            ))}
            {(data?.expensive_turns ?? []).length === 0 && <p className="text-sm text-slate-500">No turns ingested yet.</p>}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Repeated Context</h3>
          <div className="mt-3 space-y-3">
            {(data?.repeated_context ?? []).slice(0, 8).map((item) => (
              <div key={item.content_hash} className="border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
                <div className="flex justify-between gap-3">
                  <span className="font-medium">{item.category}</span>
                  <span>{item.occurrences}x</span>
                </div>
                <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">{item.preview ?? 'No preview'}</p>
                <div className="mt-1 text-xs text-slate-500">estimated tokens/block: {tokenText(item.estimated_tokens)}</div>
              </div>
            ))}
            {(data?.repeated_context ?? []).length === 0 && <p className="text-sm text-slate-500">No repeated blocks found yet.</p>}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">Sessions</h3>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-4">Agent</th>
                <th className="py-2 pr-4">Model</th>
                <th className="py-2 pr-4">Project</th>
                <th className="py-2 pr-4">Turns/events</th>
                <th className="py-2 pr-4">Tokens</th>
                <th className="py-2 pr-4">Quality</th>
              </tr>
            </thead>
            <tbody>
              {(sessions.data ?? []).map((session) => (
                <tr key={session.session_id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">{session.agent}</td>
                  <td className="py-2 pr-4">{session.model ?? 'Unavailable from source telemetry'}</td>
                  <td className="max-w-sm truncate py-2 pr-4">{session.project_path ?? 'Unavailable from source telemetry'}</td>
                  <td className="py-2 pr-4">{session.raw_event_count}</td>
                  <td className="py-2 pr-4">{tokenText(session.total_tokens)}</td>
                  <td className="py-2 pr-4">{session.token_quality}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(sessions.data ?? []).length === 0 && <p className="py-4 text-sm text-slate-500">No forensic sessions ingested yet.</p>}
        </div>
      </div>
    </section>
  )
}
