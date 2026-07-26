import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    ['verified', 'Verified'],
    ['derived', 'Derived'],
    ['estimated', 'Estimated'],
    ['stale', 'Stale'],
    ['unavailable', 'Unavailable'],
  ] as const)('renders label for quality=%s', (quality, label) => {
    render(<StatusBadge quality={quality} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
