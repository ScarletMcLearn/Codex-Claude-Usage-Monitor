import type { ReactNode } from 'react'
import { Fragment } from 'react'
import { useState } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { ForensicSessionDetail, ForensicSourceDiagnostics, ForensicTurn, ForensicTurnDetail } from '../../types/usage'

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

function timestampText(value: string | null | undefined) {
  if (!value) return 'Unavailable'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function preview(value: unknown) {
  if (typeof value !== 'string' || value.length === 0) return 'No local preview exposed'
  return value.length > 700 ? `${value.slice(0, 700)}...` : value
}

function hasLocalMessagePreview(row: { user_preview: string | null; assistant_preview: string | null }) {
  return Boolean(row.user_preview || row.assistant_preview)
}

function turnRowClass(row: { total_tokens: number | null; user_preview: string | null; assistant_preview: string | null }) {
  if (hasLocalMessagePreview(row)) {
    return 'border-emerald-300 bg-emerald-50/60 dark:border-emerald-800 dark:bg-emerald-950/20'
  }
  if (row.total_tokens != null) {
    return 'border-sky-200 bg-sky-50/40 dark:border-sky-900 dark:bg-sky-950/10'
  }
  return 'border-slate-200 dark:border-slate-800'
}

export function ForensicsPanel() {
  const queryClient = useQueryClient()
  const [active, setActive] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turnId, setTurnId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [agentFilter, setAgentFilter] = useState('')
  const [qualityFilter, setQualityFilter] = useState('reported')
  const [actualDataOnly, setActualDataOnly] = useState(true)
  const [rawExpanded, setRawExpanded] = useState(false)
  const [diagnosticsExpanded, setDiagnosticsExpanded] = useState(false)
  const [hotspotsExpanded, setHotspotsExpanded] = useState(false)
  const [showAllSessionEvents, setShowAllSessionEvents] = useState(false)
  const overview = useQuery({
    queryKey: ['forensics-overview'],
    queryFn: api.forensicOverview,
    enabled: active,
  })
  const sessions = useQuery({
    queryKey: ['forensics-sessions', offset, agentFilter, qualityFilter, actualDataOnly],
    queryFn: () => api.forensicSessions({
      offset,
      agent: agentFilter || undefined,
      token_quality: qualityFilter || undefined,
      min_total_tokens: actualDataOnly ? 1 : undefined,
    }),
    enabled: active,
  })
  const session = useQuery({
    queryKey: ['forensics-session', sessionId],
    queryFn: () => api.forensicSession(sessionId ?? ''),
    enabled: active && sessionId != null,
  })
  const turn = useQuery({
    queryKey: ['forensics-turn', turnId],
    queryFn: () => api.forensicTurn(turnId ?? ''),
    enabled: active && turnId != null,
  })
  const hotspots = useQuery({
    queryKey: ['forensics-hotspots'],
    queryFn: api.forensicHotspots,
    enabled: active && hotspotsExpanded,
  })
  const sourceDiagnostics = useQuery({
    queryKey: ['forensics-source-diagnostics'],
    queryFn: api.forensicSourceDiagnostics,
    enabled: active && diagnosticsExpanded,
  })

  async function refresh() {
    await api.forensicRefresh()
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['forensics-overview'] }),
      queryClient.invalidateQueries({ queryKey: ['forensics-sessions'] }),
      ...(hotspotsExpanded ? [queryClient.invalidateQueries({ queryKey: ['forensics-hotspots'] })] : []),
      ...(diagnosticsExpanded ? [queryClient.invalidateQueries({ queryKey: ['forensics-source-diagnostics'] })] : []),
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
  const sessionTurns = session.data?.turns ?? []
  const visibleSessionTurns = showAllSessionEvents
    ? sessionTurns
    : sessionTurns.filter((row) => (
      row.total_tokens != null ||
      row.user_preview != null ||
      row.assistant_preview != null ||
      row.token_quality === 'reported'
    ))
  const visibleFileAccesses = actualDataOnly
    ? (session.data?.file_accesses ?? []).filter((row) => (
      row.path != null ||
      row.estimated_tokens != null ||
      row.characters != null
    ))
    : (session.data?.file_accesses ?? [])

  if (!active) {
    return (
      <section aria-labelledby="section-forensics" className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="section-forensics" className="text-lg font-semibold text-slate-800 dark:text-slate-100">
              Token Forensics
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Large local evidence view. Load only when needed to keep dashboard fast.
            </p>
          </div>
          <button className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900" onClick={() => setActive(true)}>
            Open token forensics
          </button>
        </div>
      </section>
    )
  }

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
          <button className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700" onClick={() => setActive(false)}>
            Close forensics
          </button>
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

      <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">Collector Diagnostics</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Collection mode: Passive local telemetry
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
            <span>Model-generation requests by forensic monitor: {data?.zero_token_counters.monitor_model_generation_requests ?? 0}</span>
            <button className="rounded-md border border-slate-300 px-3 py-1 dark:border-slate-700" onClick={() => setDiagnosticsExpanded((value) => !value)}>
              {diagnosticsExpanded ? 'Hide diagnostics' : 'Load diagnostics'}
            </button>
          </div>
        </div>
        {!diagnosticsExpanded ? (
          <p className="mt-3 text-sm text-slate-500">Source diagnostics are hidden until requested.</p>
        ) : sourceDiagnostics.isError ? (
          <p className="mt-3 text-sm text-red-600">Source diagnostics unavailable.</p>
        ) : (
          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
            {(sourceDiagnostics.data ?? []).map((source) => (
              <SourceDiagnosticCard key={source.source_id} source={source} />
            ))}
            {(sourceDiagnostics.data ?? []).length === 0 && (
              <p className="text-sm text-slate-500">No passive telemetry sources discovered yet.</p>
            )}
          </div>
        )}
      </div>

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
            <button className={`rounded-md border px-3 py-1 ${actualDataOnly ? 'border-emerald-300 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-slate-700'}`} onClick={() => { setOffset(0); setActualDataOnly((value) => !value) }}>
              {actualDataOnly ? 'Actual data only' : 'Include unknown'}
            </button>
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
          {actualDataOnly && (
            <p className="mb-2 text-xs text-slate-500">
              Hiding sessions with unavailable tokens. Turn off "Actual data only" to inspect unknown raw fragments.
            </p>
          )}
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-4">Timestamp</th>
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
                <Fragment key={row.session_id}>
                  <tr className="border-t border-slate-100 dark:border-slate-800">
                    <td className="whitespace-nowrap py-2 pr-4">{timestampText(row.started_at_utc ?? row.ended_at_utc)}</td>
                    <td className="py-2 pr-4">
                      <button
                        className="font-medium text-slate-900 underline-offset-2 hover:underline dark:text-slate-50"
                        aria-expanded={sessionId === row.session_id}
                        onClick={() => { setSessionId((current) => current === row.session_id ? null : row.session_id); setTurnId(null) }}
                      >
                        {row.agent}
                      </button>
                    </td>
                    <td className="py-2 pr-4">{row.model ?? 'Unavailable'}</td>
                    <td className="max-w-sm truncate py-2 pr-4">{row.project_path ?? 'Unavailable'}</td>
                    <td className="py-2 pr-4">{row.raw_event_count}</td>
                    <td className="py-2 pr-4">{tokenText(row.total_tokens)}</td>
                    <td className="py-2 pr-4">{qualityText(row.token_quality)}</td>
                  </tr>
                  {sessionId === row.session_id && (
                    <tr className="border-t border-slate-100 dark:border-slate-800">
                      <td colSpan={7} className="bg-slate-50/60 p-3 dark:bg-slate-950/20">
                        {session.isLoading ? (
                          <p className="text-sm text-slate-500">Loading session evidence...</p>
                        ) : session.data ? (
                          <SessionDrillDown
                            actualDataOnly={actualDataOnly}
                            rawExpanded={rawExpanded}
                            sessionData={session.data}
                            showAllSessionEvents={showAllSessionEvents}
                            turn={turn}
                            turnDetail={turnDetail}
                            turnId={turnId}
                            visibleFileAccesses={visibleFileAccesses}
                            visibleSessionTurns={visibleSessionTurns}
                            onToggleRaw={() => setRawExpanded((value) => !value)}
                            onToggleShowAllSessionEvents={() => setShowAllSessionEvents((value) => !value)}
                            onTurnClick={(selectedTurnId) => setTurnId((current) => current === selectedTurnId ? null : selectedTurnId)}
                          />
                        ) : session.isError ? (
                          <p className="text-sm text-red-600">Session evidence unavailable.</p>
                        ) : null}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {(sessions.data?.items ?? []).length === 0 && (
            <p className="py-4 text-sm text-slate-500">
              {actualDataOnly ? 'No sessions with reported token totals match these filters.' : 'No forensic sessions ingested yet.'}
            </p>
          )}
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

      <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Hotspots</h3>
          <button className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-700" onClick={() => setHotspotsExpanded((value) => !value)}>
            {hotspotsExpanded ? 'Hide hotspots' : 'Load hotspots'}
          </button>
        </div>
        {hotspotsExpanded ? (
          <div className="mt-3 grid grid-cols-1 gap-4 xl:grid-cols-3">
            <Hotspot title="Tool Hotspots" rows={hotspots.data?.tools ?? []} nameKey="tool_name" />
            <Hotspot title="Command Hotspots" rows={hotspots.data?.commands ?? []} nameKey="command" />
            <Hotspot title="Context Hotspots" rows={hotspots.data?.context ?? []} nameKey="category" />
            <Hotspot title="File Hotspots" rows={hotspots.data?.files ?? []} nameKey="path" />
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">Hotspot analysis is hidden until requested.</p>
        )}
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

function SessionDrillDown({
  actualDataOnly,
  rawExpanded,
  sessionData,
  showAllSessionEvents,
  turn,
  turnDetail,
  turnId,
  visibleFileAccesses,
  visibleSessionTurns,
  onToggleRaw,
  onToggleShowAllSessionEvents,
  onTurnClick,
}: {
  actualDataOnly: boolean
  rawExpanded: boolean
  sessionData: ForensicSessionDetail
  showAllSessionEvents: boolean
  turn: UseQueryResult<ForensicTurnDetail, Error>
  turnDetail: ForensicTurnDetail | undefined
  turnId: string | null
  visibleFileAccesses: Array<Record<string, unknown>>
  visibleSessionTurns: ForensicTurn[]
  onToggleRaw: () => void
  onToggleShowAllSessionEvents: () => void
  onTurnClick: (turnId: string) => void
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Session Drill-Down</h3>
          <p className="mt-1 text-xs text-slate-500">{sessionData.session.session_id}</p>
          {actualDataOnly && (
            <p className="mt-1 text-xs text-slate-500">
              Showing turns with tokens or local text previews.
            </p>
          )}
        </div>
        <button className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-700" onClick={onToggleShowAllSessionEvents}>
          {showAllSessionEvents ? 'Show evidence only' : 'Show all raw events'}
        </button>
      </div>
      <div className="mt-3 grid gap-2">
        {visibleSessionTurns.map((row) => (
          <div key={row.turn_id} className={`rounded-md border ${turnRowClass(row)}`}>
            <button className="block w-full p-3 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-900" onClick={() => onTurnClick(row.turn_id)}>
              <div className="flex flex-wrap justify-between gap-2">
                <span>
                  Turn {row.turn_index} · {row.event_type ?? 'event'} · {row.model ?? sessionData.session.model ?? 'unknown model'}
                  {hasLocalMessagePreview(row) ? ' · messages' : ''}
                </span>
                <span>{tokenText(row.total_tokens)} · {qualityText(row.token_quality)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">
                {row.user_preview || row.assistant_preview || (row.total_tokens != null ? 'Usage-only record; prompt/output preview is on neighboring message events when exposed.' : 'No local preview exposed')}
              </p>
            </button>
            {turnId === row.turn_id && (
              <div className="border-t border-slate-200 p-3 dark:border-slate-800">
                {turn.isLoading ? (
                  <p className="text-sm text-slate-500">Loading turn evidence...</p>
                ) : turnDetail ? (
                  <TurnEvidence detail={turnDetail} rawExpanded={rawExpanded} onToggleRaw={onToggleRaw} />
                ) : turn.isError ? (
                  <p className="text-sm text-red-600">Turn evidence unavailable.</p>
                ) : null}
              </div>
            )}
          </div>
        ))}
        {visibleSessionTurns.length === 0 && (
          <p className="rounded-md border border-slate-200 p-3 text-sm text-slate-500 dark:border-slate-800">
            No token-bearing or preview-bearing events in this session. Use "Show all raw events" to inspect metadata.
          </p>
        )}
      </div>
      <EvidenceList title="File Access">
        {visibleFileAccesses.map((row, index) => (
          <button key={index} className="block w-full rounded-md border border-slate-200 p-3 text-left text-sm hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900" onClick={() => row.turn_id && onTurnClick(String(row.turn_id))}>
            <div className="font-medium">{textValue(row.path)}</div>
            <div className="text-xs text-slate-500">
              {textValue(row.operation)} · {textValue(row.actual_range)} · chars {textValue(row.characters)} · tokens {tokenText(row.estimated_tokens as number | null)} · Quality {qualityText(row.token_quality)}
            </div>
            <div className="text-xs text-slate-500">
              repeated path {textValue(row.repeated_path)} · repeated content {textValue(row.repeated_content)}
            </div>
          </button>
        ))}
        {visibleFileAccesses.length === 0 && <p className="text-sm text-slate-500">No explicit file access evidence.</p>}
      </EvidenceList>
      <EvidenceList title="Relationships">
        {sessionData.relationships.map((row, index) => (
          <pre key={index} className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
            {preview(JSON.stringify(row, null, 2))}
          </pre>
        ))}
        {sessionData.relationships.length === 0 && <p className="text-sm text-slate-500">No parent/child evidence.</p>}
      </EvidenceList>
    </div>
  )
}

function TurnEvidence({
  detail,
  rawExpanded,
  onToggleRaw,
}: {
  detail: ForensicTurnDetail
  rawExpanded: boolean
  onToggleRaw: () => void
}) {
  const supportingRows = [
    ...detail.tools,
    ...detail.commands,
    ...detail.file_accesses,
    ...detail.context_blocks,
  ]

  return (
    <div className="space-y-3">
      <h4 className="font-semibold text-slate-800 dark:text-slate-100">Turn Evidence</h4>
      <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        <Metric label="Input" value={tokenText(detail.turn.input_tokens)} />
        <Metric label="Output" value={tokenText(detail.turn.output_tokens)} />
        <Metric label="Cache" value={tokenText(detail.turn.cached_tokens)} />
        <Metric label="Reasoning" value={tokenText(detail.turn.reasoning_tokens)} />
      </div>
      <EvidenceList title="Input / Output">
        {detail.messages.map((row, index) => (
          <pre key={`${textValue(row.message_id)}-${index}`} className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
            {textValue(row.role)} · {qualityText(row.token_quality)} · {tokenText(row.estimated_tokens as number | null)}
            {'\n\n'}
            {preview(row.preview)}
          </pre>
        ))}
        {detail.messages.length === 0 && <p className="text-sm text-slate-500">No local input/output text exposed for this turn.</p>}
      </EvidenceList>
      <EvidenceList title="Tools / Commands / Context">
        {supportingRows.map((row, index) => (
          <pre key={index} className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
            {preview(JSON.stringify(row, null, 2))}
          </pre>
        ))}
        {supportingRows.length === 0 && <p className="text-sm text-slate-500">No tool, command, file, or context rows exposed for this turn.</p>}
      </EvidenceList>
      <EvidenceList title="Raw / Provenance">
        <button className="rounded-md border border-slate-300 px-3 py-1 text-sm dark:border-slate-700" onClick={onToggleRaw}>
          {rawExpanded ? 'Collapse raw provenance' : 'Expand raw provenance'}
        </button>
        {rawExpanded ? (
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs dark:bg-slate-900">
            {preview(detail.turn.provenance_json)}
            {'\n\n'}
            {preview(JSON.stringify(detail.raw_events, null, 2))}
          </pre>
        ) : (
          <p className="text-sm text-slate-500">Raw and provenance data hidden until requested.</p>
        )}
      </EvidenceList>
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

function SourceDiagnosticCard({ source }: { source: ForensicSourceDiagnostics }) {
  const health = sourceHealth(source)
  return (
    <div className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-medium text-slate-900 dark:text-slate-50">
            {textValue(source.source)} · {textValue(source.source_type)}
          </div>
          <div className="mt-1 break-all text-xs text-slate-500">
            Source identity: {textValue(source.source_identity)}
          </div>
        </div>
        <span className={`rounded-md border px-2 py-1 text-xs ${healthClass(health.state)}`}>
          {health.state}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
        <DiagnosticMetric label="Parser version" value={textValue(source.parser_version)} />
        <DiagnosticMetric label="File size" value={tokenText(source.file_size)} />
        <DiagnosticMetric label="Checkpoint offset" value={tokenText(source.stored_checkpoint)} />
        <DiagnosticMetric label="Processed events" value={tokenText(source.events_processed)} />
        <DiagnosticMetric label="Duplicates skipped" value={tokenText(source.duplicate_events)} />
        <DiagnosticMetric label="Malformed events" value={tokenText(source.malformed_events)} />
        <DiagnosticMetric label="Reset count" value={tokenText(source.checkpoint_reset_count)} />
        <DiagnosticMetric label="Reset reason" value={textValue(source.reset_reason)} />
        <DiagnosticMetric label="Last event timestamp" value={textValue(source.last_event_time_utc)} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <DiagnosticFlag label="Rotation detected" active={Boolean(source.rotation_detected)} />
        <DiagnosticFlag label="Truncation detected" active={Boolean(source.truncation_detected)} />
        <DiagnosticFlag label="Replacement detected" active={Boolean(source.replacement_detected)} />
      </div>
      <p className="mt-2 text-xs text-slate-500">{health.reason}</p>
    </div>
  )
}

function DiagnosticMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-50 p-2 dark:bg-slate-900">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words font-medium text-slate-800 dark:text-slate-100">{value}</div>
    </div>
  )
}

function DiagnosticFlag({ label, active }: { label: string; active: boolean }) {
  return (
    <span className={`rounded-md border px-2 py-1 ${active ? 'border-amber-300 text-amber-700 dark:text-amber-200' : 'border-slate-200 text-slate-500 dark:border-slate-800'}`}>
      {label}: {active ? 'Yes' : 'No'}
    </span>
  )
}

function sourceHealth(source: ForensicSourceDiagnostics): { state: 'Healthy' | 'Idle' | 'Warning' | 'Error'; reason: string } {
  if (source.last_error) return { state: 'Error', reason: `Collector error: ${source.last_error}` }
  if (
    source.malformed_events > 0 ||
    source.checkpoint_reset_count > 0 ||
    Boolean(source.rotation_detected) ||
    Boolean(source.truncation_detected) ||
    Boolean(source.replacement_detected)
  ) {
    return { state: 'Warning', reason: 'Source has malformed, reset, rotation, truncation, or replacement evidence.' }
  }
  if (source.events_processed > 0) return { state: 'Healthy', reason: 'Source accessible and events processed without current parser errors.' }
  return { state: 'Idle', reason: 'Source valid and unchanged; no new local telemetry ingested.' }
}

function healthClass(state: ReturnType<typeof sourceHealth>['state']) {
  if (state === 'Healthy') return 'border-emerald-300 text-emerald-700 dark:text-emerald-200'
  if (state === 'Idle') return 'border-slate-300 text-slate-600 dark:text-slate-300'
  if (state === 'Warning') return 'border-amber-300 text-amber-700 dark:text-amber-200'
  return 'border-red-300 text-red-700 dark:text-red-200'
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
