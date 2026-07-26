import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SkeletonCard } from './SkeletonCard'

describe('SkeletonCard', () => {
  it('renders a status role for accessibility during loading', () => {
    render(<SkeletonCard />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
