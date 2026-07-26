import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UsageBar } from './UsageBar'

describe('UsageBar', () => {
  it('shows Normal level with percentage text for low usage', () => {
    render(<UsageBar usedPercent={20} quality="verified" label="5-hour" />)
    expect(screen.getByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('20%')).toBeInTheDocument()
  })

  it('shows Critical level for 95%+', () => {
    render(<UsageBar usedPercent={96} quality="verified" label="5-hour" />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('shows Exhausted level at 100%', () => {
    render(<UsageBar usedPercent={100} quality="verified" label="5-hour" />)
    expect(screen.getByText('Exhausted')).toBeInTheDocument()
  })

  it('shows Unknown and no percentage when quality is unavailable, never a fabricated 0%', () => {
    render(
      <UsageBar
        usedPercent={null}
        quality="unavailable"
        unavailableReason="No data available"
        label="5-hour"
      />
    )
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.getByText('No data available')).toBeInTheDocument()
  })

  it('exposes an accessible progressbar role with a text label (not color alone)', () => {
    render(<UsageBar usedPercent={42} quality="verified" label="5-hour" />)
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '42')
    expect(bar.getAttribute('aria-label')).toContain('Normal')
  })
})
