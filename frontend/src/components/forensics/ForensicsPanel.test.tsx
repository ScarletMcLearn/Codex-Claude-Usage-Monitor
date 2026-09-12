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
