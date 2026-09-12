import type { ReactNode } from 'react'
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

function tokenText(value: number | null | undefined) {
  return value == null ? 'Unavailable' : value.toLocaleString()
}

function textValue(value: unknown) {
  if (value == null || value === '') return 'Unavailable'
  return String(value)
}

function qualityText(value: unknown) {
  const raw = String(value ?? 'unknown')
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

function preview(value: unknown) {
  if (typeof value !== 'string' || value.length === 0) return 'No local preview exposed'
  return value.length > 700 ? `${value.slice(0, 700)}...` : value
}

export function ForensicsPanel() {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turnId, setTurnId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [agentFilter, setAgentFilter] = useState('')
  const [qualityFilter, setQualityFilter] = useState('')
  const [rawExpanded, setRawExpanded] = useState(false)
  const overview = useQuery({ queryKey: ['forensics-overview'], queryFn: api.forensicOverview })
  const sessions = useQuery({
    queryKey: ['forensics-sessions', offset, agentFilter, qualityFilter],
    queryFn: () => api.forensicSessions({
      offset,
      agent: agentFilter || undefined,
      token_quality: qualityFilter || undefined,
    }),
  })
  const session = useQuery({
    queryKey: ['forensics-session', sessionId],
    queryFn: () => api.forensicSession(sessionId ?? ''),
    enabled: sessionId != null,
  })
  const turn = useQuery({
    queryKey: ['forensics-turn', turnId],
    queryFn: () => api.forensicTurn(turnId ?? ''),
    enabled: turnId != null,
  })
  const hotspots = useQuery({ queryKey: ['forensics-hotspots'], queryFn: api.forensicHotspots })

  async function refresh() {
    await api.forensicRefresh()
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['forensics-overview'] }),
      queryClient.invalidateQueries({ queryKey: ['forensics-sessions'] }),
      queryClient.invalidateQueries({ queryKey: ['forensics-hotspots'] }),
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
  const turnDetail = turn.data

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
        <EvidenceList title="Expensive Turns">
          {(data?.expensive_turns ?? []).slice(0, 8).map((item) => (
            <button key={item.turn_id} className="block w-full border-t border-slate-100 pt-3 text-left text-sm dark:border-slate-800" onClick={() => setTurnId(item.turn_id)}>
              <div className="flex justify-between gap-3">
                  <span className="font-medium">{item.model ?? item.event_type ?? 'Unknown model'}</span>
                <span>{tokenText(item.total_tokens)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">
                {item.user_preview || item.assistant_preview || 'No local preview exposed'}
              </p>
              <div className="mt-1 text-xs text-slate-500">Quality: {qualityText(item.token_quality)}</div>
            </button>
          ))}
          {(data?.expensive_turns ?? []).length === 0 && <p className="text-sm text-slate-500">No turns ingested yet.</p>}
        </EvidenceList>

        <EvidenceList title="Repeated Context">
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
        </EvidenceList>
      </div>

      <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Sessions</h3>
          <div className="flex flex-wrap gap-2 text-sm">
            <select className="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" value={agentFilter} onChange={(event) => { setOffset(0); setAgentFilter(event.target.value) }}>
              <option value="">All agents</option>
              <option value="codex">Codex</option>
              <option value="claude">Claude</option>
              <option value="free_ai">Free-AI</option>
              <option value="antigravity">Antigravity</option>
            </select>
            <select className="rounded-md border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-700" value={qualityFilter} onChange={(event) => { setOffset(0); setQualityFilter(event.target.value) }}>
              <option value="">All qualities</option>
              <option value="reported">Reported</option>
              <option value="derived">Derived</option>
              <option value="estimated">Estimated</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
        </div>
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
              {(sessions.data?.items ?? []).map((row) => (
                <tr key={row.session_id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">
                    <button className="font-medium text-slate-900 underline-offset-2 hover:underline dark:text-slate-50" onClick={() => { setSessionId(row.session_id); setTurnId(null) }}>
                      {row.agent}
                    </button>
                  </td>
                  <td className="py-2 pr-4">{row.model ?? 'Unavailable'}</td>
                  <td className="max-w-sm truncate py-2 pr-4">{row.project_path ?? 'Unavailable'}</td>
                  <td className="py-2 pr-4">{row.raw_event_count}</td>
                  <td className="py-2 pr-4">{tokenText(row.total_tokens)}</td>
                  <td className="py-2 pr-4">{qualityText(row.token_quality)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(sessions.data?.items ?? []).length === 0 && <p className="py-4 text-sm text-slate-500">No forensic sessions ingested yet.</p>}
        </div>
        <div className="mt-3 flex items-center justify-between text-sm">
          <button className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40 dark:border-slate-700" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>
            Previous
          </button>
          <span>Offset {sessions.data?.offset ?? offset}</span>
          <button className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40 dark:border-slate-700" disabled={!sessions.data?.has_more} onClick={() => setOffset(offset + 50)}>
            Next
          </button>
        </div>
      </div>

      {session.data && (
        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Session Drill-Down</h3>
          <p className="mt-1 text-xs text-slate-500">{session.data.session.session_id}</p>
          <div className="mt-3 grid gap-2">
            {session.data.turns.map((row) => (
              <button key={row.turn_id} className="rounded-md border border-slate-200 p-3 text-left text-sm hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900" onClick={() => setTurnId(row.turn_id)}>
                <div className="flex flex-wrap justify-between gap-2">
                  <span>Turn {row.turn_index} · {row.event_type ?? 'event'} · {row.model ?? 'unknown model'}</span>
                  <span>{tokenText(row.total_tokens)} · {qualityText(row.token_quality)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">{row.user_preview || row.assistant_preview || 'No local preview exposed'}</p>
              </button>
            ))}
          </div>
          <EvidenceList title="File Access">
            {session.data.file_accesses.map((row, index) => (
              <button key={index} className="block w-full rounded-md border border-slate-200 p-3 text-left text-sm hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900" onClick={() => row.turn_id && setTurnId(String(row.turn_id))}>
                <div className="font-medium">{textValue(row.path)}</div>
                <div className="text-xs text-slate-500">
                  {textValue(row.operation)} · {textValue(row.actual_range)} · chars {textValue(row.characters)} · tokens {tokenText(row.estimated_tokens as number | null)} · Quality {qualityText(row.token_quality)}
                </div>
                <div className="text-xs text-slate-500">
                  repeated path {textValue(row.repeated_path)} · repeated content {textValue(row.repeated_content)}
                </div>
              </button>
            ))}
            {session.data.file_accesses.length === 0 && <p className="text-sm text-slate-500">No explicit file access evidence.</p>}
          </EvidenceList>
          <EvidenceList title="Relationships">
            {session.data.relationships.map((row, index) => (
              <pre key={index} className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
                {preview(JSON.stringify(row, null, 2))}
              </pre>
            ))}
            {session.data.relationships.length === 0 && <p className="text-sm text-slate-500">No parent/child evidence.</p>}
          </EvidenceList>
        </div>
      )}

      {turnDetail && (
        <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Turn Evidence</h3>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
            <Metric label="Input" value={tokenText(turnDetail.turn.input_tokens)} />
            <Metric label="Output" value={tokenText(turnDetail.turn.output_tokens)} />
            <Metric label="Cache" value={tokenText(turnDetail.turn.cached_tokens)} />
            <Metric label="Reasoning" value={tokenText(turnDetail.turn.reasoning_tokens)} />
          </div>
          <EvidenceList title="Input / Output">
            {turnDetail.messages.map((row, index) => (
              <pre key={`${textValue(row.message_id)}-${index}`} className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
                {textValue(row.role)} · {qualityText(row.token_quality)} · {tokenText(row.estimated_tokens as number | null)}
                {'\n\n'}
                {preview(row.preview)}
              </pre>
            ))}
          </EvidenceList>
          <EvidenceList title="Tools / Commands / Context">
            {[...turnDetail.tools, ...turnDetail.commands, ...turnDetail.file_accesses, ...turnDetail.context_blocks].map((row, index) => (
              <pre key={index} className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
                {preview(JSON.stringify(row, null, 2))}
              </pre>
            ))}
          </EvidenceList>
          <EvidenceList title="Raw / Provenance">
            <button className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-700" onClick={() => setRawExpanded((value) => !value)}>
              {rawExpanded ? 'Collapse raw provenance' : 'Expand raw provenance'}
            </button>
            {rawExpanded ? (
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
                {preview(turnDetail.turn.provenance_json)}
                {'\n\n'}
                {preview(JSON.stringify(turnDetail.raw_events, null, 2))}
              </pre>
            ) : (
              <p className="text-sm text-slate-500">Raw and provenance data hidden until requested.</p>
            )}
          </EvidenceList>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Hotspot title="Tool Hotspots" rows={hotspots.data?.tools ?? []} nameKey="tool_name" />
        <Hotspot title="Command Hotspots" rows={hotspots.data?.commands ?? []} nameKey="command" />
        <Hotspot title="Context Hotspots" rows={hotspots.data?.context ?? []} nameKey="category" />
        <Hotspot title="File Hotspots" rows={hotspots.data?.files ?? []} nameKey="path" />
      </div>
    </section>
  )
}

function EvidenceList({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
      <h3 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
      <div className="mt-3 space-y-3">{children}</div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 p-2 dark:border-slate-800">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}

function Hotspot({ title, rows, nameKey }: { title: string; rows: Array<Record<string, unknown>>; nameKey: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
      <h3 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
      <div className="mt-3 space-y-2 text-sm">
        {rows.slice(0, 8).map((row, index) => (
          <div key={index} className="border-t border-slate-100 pt-2 dark:border-slate-800">
            <div className="truncate font-medium">{textValue(row[nameKey])}</div>
            <div className="text-xs text-slate-500">
              {textValue(row.calls ?? row.occurrences)} uses · {textValue(row.output_bytes ?? row.bytes)} bytes · failures {textValue(row.failures ?? 0)}
            </div>
          </div>
        ))}
        {rows.length === 0 && <p className="text-slate-500">Unavailable</p>}
      </div>
    </div>
  )
}
