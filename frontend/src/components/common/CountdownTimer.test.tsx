import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CountdownTimer } from './CountdownTimer'

describe('CountdownTimer', () => {
  it('shows Unknown when targetIso is null, never a fabricated countdown', () => {
    render(<CountdownTimer targetIso={null} />)
    expect(screen.getByTestId('countdown-unknown')).toHaveTextContent('Unknown')
  })

  it('shows a countdown and local time when targetIso is provided', () => {
    const future = new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()
    render(<CountdownTimer targetIso={future} displayTimeZone="Asia/Dhaka" />)
    const el = screen.getByTestId('countdown')
    expect(el.textContent).toMatch(/h/)
  })
})
