import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No profiles" description="Nothing discovered yet." />)
    expect(screen.getByText('No profiles')).toBeInTheDocument()
    expect(screen.getByText('Nothing discovered yet.')).toBeInTheDocument()
  })

  it('renders without description', () => {
    render(<EmptyState title="No history" />)
    expect(screen.getByText('No history')).toBeInTheDocument()
  })
})
