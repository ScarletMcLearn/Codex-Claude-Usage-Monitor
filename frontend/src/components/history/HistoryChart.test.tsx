import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HistoryChart } from './HistoryChart'
import type { HistoryRow } from '../../types/usage'

describe('HistoryChart', () => {
  it('shows an empty state when there are no rows', () => {
    render(<HistoryChart rows={[]} />)
    expect(screen.getByText('No history yet')).toBeInTheDocument()
  })

  it('renders a chart container when rows are present', () => {
    const rows: HistoryRow[] = [
      {
        id: 1,
        profile_key: 'claude:p1',
        window_id: 'five_hour',
        window_label: '5-hour',
        used_percent: 42,
        remaining_percent: 58,
        resets_at_utc: null,
        reset_confirmed: 0,
        quality: 'verified',
        unavailable_reason: null,
        observed_at_utc: new Date().toISOString(),
        source_detail_json: null,
        is_reset_boundary: 0,
        provider: 'claude',
        profile_label: 'default',
        friendly_name: null,
      },
    ]
    render(<HistoryChart rows={rows} />)
    expect(screen.getByTestId('history-chart')).toBeInTheDocument()
  })
})
