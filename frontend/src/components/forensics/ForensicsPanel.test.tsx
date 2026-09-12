import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { ForensicsPanel } from './ForensicsPanel'

vi.mock('../../api/client', () => ({
  api: {
    forensicOverview: vi.fn().mockResolvedValue({
      counts: { forensic_sessions: 1 },
      agents: [],
      expensive_turns: [{
        turn_id: 't1',
        session_id: 's1',
        event_type: 'assistant',
        timestamp_utc: '2026-09-12T00:00:00Z',
        model: 'claude-test',
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
        token_quality: 'reported',
        user_preview: 'ask',
        assistant_preview: 'answer',
      }],
      repeated_context: [],
      zero_token_counters: {
        monitor_model_generation_requests: 0,
        monitor_completion_requests: 0,
        monitor_agent_prompt_invocations: 0,
      },
    }),
    forensicSessions: vi.fn().mockResolvedValue({
      items: [{
        session_id: 's1',
        agent: 'claude',
        provider: 'anthropic',
        model: 'claude-test',
        project_path: '/repo',
        started_at_utc: '2026-09-12T00:00:00Z',
        ended_at_utc: '2026-09-12T00:00:01Z',
        raw_event_count: 2,
        input_tokens: 10,
        output_tokens: 5,
        total_tokens: 15,
        token_quality: 'reported',
      }],
      limit: 50,
      offset: 0,
      has_more: false,
    }),
    forensicSession: vi.fn().mockResolvedValue({
      session: { session_id: 's1', agent: 'claude' },
      turns: [{
        turn_id: 't1',
        session_id: 's1',
        turn_index: 1,
        event_type: 'assistant',
        timestamp_utc: '2026-09-12T00:00:01Z',
        model: 'claude-test',
        input_tokens: null,
        output_tokens: 0,
        total_tokens: 0,
        cached_tokens: 0,
        cache_write_tokens: 0,
        reasoning_tokens: null,
        context_tokens: null,
        token_quality: 'reported',
        user_preview: 'ask',
        assistant_preview: 'answer',
        raw_event_id: 'r1',
      }],
      tools: [],
      commands: [],
      context_blocks: [],
      file_accesses: [{
        path: 'README.md',
        operation: 'Read',
        actual_range: '1..20',
        characters: 120,
        estimated_tokens: 30,
        token_quality: 'estimated',
        repeated_path: 1,
        repeated_content: 0,
        turn_id: 't1',
      }],
      relationships: [{ relationship_type: 'parent_message', child_turn_id: 't1' }],
    }),
    forensicTurn: vi.fn().mockResolvedValue({
      session: { session_id: 's1', agent: 'claude' },
      turn: {
        turn_id: 't1',
        session_id: 's1',
        turn_index: 1,
        event_type: 'assistant',
        timestamp_utc: '2026-09-12T00:00:01Z',
        model: 'claude-test',
        input_tokens: null,
        output_tokens: 0,
        total_tokens: 0,
        cached_tokens: 0,
        cache_write_tokens: 0,
        reasoning_tokens: null,
        context_tokens: null,
        token_quality: 'reported',
        user_preview: 'ask',
        assistant_preview: 'answer',
        raw_event_id: 'r1',
        provenance_json: '{"token_semantics":"per_request"}',
      },
      messages: [{ message_id: 'm1', role: 'assistant', token_quality: 'estimated', estimated_tokens: 4, preview: 'answer' }],
      tools: [],
      commands: [],
      context_blocks: [],
      file_accesses: [{ path: 'README.md', operation: 'Read' }],
      relationships: [{ relationship_type: 'parent_message' }],
      raw_events: [{ raw_event_id: 'r1', event_type: 'assistant', raw_json: '{"secret":"hidden"}' }],
    }),
    forensicHotspots: vi.fn().mockResolvedValue({
      tools: [],
      commands: [],
      context: [],
      files: [{ path: 'README.md', accesses: 2, characters: 120, estimated_tokens: 30 }],
    }),
    forensicSourceDiagnostics: vi.fn().mockResolvedValue([
      {
        source_id: 'healthy-src',
        source: 'codex',
        source_type: 'jsonl',
        source_identity: 'codex-session-a.jsonl',
        file_size: 2048,
        stored_checkpoint: 2048,
        current_offset: 2048,
        last_event_time_utc: '2026-09-12T00:00:01Z',
        parser_version: 'codex-jsonl-v1',
        events_processed: 2,
        malformed_events: 0,
        duplicate_events: 0,
        checkpoint_reset_count: 0,
        reset_reason: null,
        rotation_detected: 0,
        truncation_detected: 0,
        replacement_detected: 0,
        last_error: null,
      },
      {
        source_id: 'idle-src',
        source: 'claude',
        source_type: 'jsonl',
        source_identity: null,
        file_size: null,
        stored_checkpoint: null,
        current_offset: null,
        last_event_time_utc: null,
        parser_version: 'claude-jsonl-v1',
        events_processed: 0,
        malformed_events: 0,
        duplicate_events: 0,
        checkpoint_reset_count: 0,
        reset_reason: null,
        rotation_detected: 0,
        truncation_detected: 0,
        replacement_detected: 0,
        last_error: null,
      },
      {
        source_id: 'warning-src',
        source: 'codex',
        source_type: 'jsonl',
        source_identity: 'sanitized-warning-source',
        file_size: 4096,
        stored_checkpoint: 128,
        current_offset: 128,
        last_event_time_utc: '2026-09-12T00:00:02Z',
        parser_version: 'codex-jsonl-v2',
        events_processed: 4,
        malformed_events: 3,
        duplicate_events: 2,
        checkpoint_reset_count: 1,
        reset_reason: 'file replacement detected',
        rotation_detected: 0,
        truncation_detected: 1,
        replacement_detected: 1,
        last_error: null,
      },
    ]),
    forensicRefresh: vi.fn(),
    forensicExport: vi.fn().mockResolvedValue({ path: '/tmp/export.zip' }),
  },
}))

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ForensicsPanel />
    </QueryClientProvider>
  )
}

describe('ForensicsPanel', () => {
  it('drills into session and turn evidence including file and relationship rows', async () => {
    renderPanel()

    fireEvent.click(await screen.findByText('claude'))
    expect(await screen.findByText('Session Drill-Down')).toBeInTheDocument()
    expect((await screen.findAllByText('README.md')).length).toBeGreaterThan(0)
    expect(screen.getByText(/parent_message/)).toBeInTheDocument()

    fireEvent.click(screen.getByText(/Turn 1/))
    expect(await screen.findByText('Turn Evidence')).toBeInTheDocument()
    expect(screen.getByText('Raw and provenance data hidden until requested.')).toBeInTheDocument()
    expect(screen.queryByText(/per_request/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Expand raw provenance'))
    expect(screen.getByText(/per_request/)).toBeInTheDocument()
    expect(screen.getByText(/hidden/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Collapse raw provenance'))
    expect(screen.queryByText(/per_request/)).not.toBeInTheDocument()
    expect(screen.getByText('File Hotspots')).toBeInTheDocument()
  })

  it('renders filter controls and pagination state', async () => {
    renderPanel()

    await waitFor(() => expect(screen.getByText('Sessions')).toBeInTheDocument())
    expect(screen.getByDisplayValue('All agents')).toBeInTheDocument()
    expect(screen.getByDisplayValue('All qualities')).toBeInTheDocument()
    expect(screen.getByText('Offset 0')).toBeInTheDocument()
  })

  it('renders deterministic source diagnostics without raw conversation text', async () => {
    renderPanel()

    expect(await screen.findByText('Collector Diagnostics')).toBeInTheDocument()
    expect(screen.getByText('Collection mode: Passive local telemetry')).toBeInTheDocument()
    expect(screen.getByText('Model-generation requests by forensic monitor: 0')).toBeInTheDocument()
    expect(await screen.findByText('codex-jsonl-v1')).toBeInTheDocument()
    expect(await screen.findByText('claude-jsonl-v1')).toBeInTheDocument()
    expect(await screen.findByText('codex-jsonl-v2')).toBeInTheDocument()
    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText('Idle')).toBeInTheDocument()
    expect(screen.getByText('Warning')).toBeInTheDocument()
    expect(screen.queryByText('Error')).not.toBeInTheDocument()
    expect(screen.getByText('Source valid and unchanged; no new local telemetry ingested.')).toBeInTheDocument()
    expect(screen.getAllByText('3').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1').length).toBeGreaterThan(0)
    expect(screen.getByText('file replacement detected')).toBeInTheDocument()
    expect(screen.getByText('Truncation detected: Yes')).toBeInTheDocument()
    expect(screen.getByText('Replacement detected: Yes')).toBeInTheDocument()
    expect(screen.getByText('Source identity: Unavailable')).toBeInTheDocument()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.queryByText('user private prompt')).not.toBeInTheDocument()
    expect(screen.queryByText('assistant private response')).not.toBeInTheDocument()
    expect(screen.queryByText('raw command output')).not.toBeInTheDocument()
  })

  it('gates full export with warning acknowledgement', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    renderPanel()

    fireEvent.click(await screen.findByText('Full forensic export'))
    expect(api.forensicExport).not.toHaveBeenCalled()

    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByText('Full forensic export'))
    await waitFor(() => expect(api.forensicExport).toHaveBeenCalledWith('full', true))

    fireEvent.click(screen.getByText('Summary export'))
    await waitFor(() => expect(api.forensicExport).toHaveBeenCalledWith('summary', false))
    confirm.mockRestore()
    alert.mockRestore()
  })

  it('distinguishes unavailable from zero and estimated from reported', async () => {
    renderPanel()

    fireEvent.click(await screen.findByText('claude'))
    fireEvent.click(await screen.findByText(/Turn 1/))

    expect(await screen.findByText('Turn Evidence')).toBeInTheDocument()
    expect(screen.getByText('Input').nextSibling?.textContent).toBe('Unavailable')
    expect(screen.getByText('Output').nextSibling?.textContent).toBe('0')
    expect(screen.getByText(/assistant · Estimated · 4/)).toBeInTheDocument()
    expect(screen.getAllByText(/Reported/).length).toBeGreaterThan(0)
  })
})
