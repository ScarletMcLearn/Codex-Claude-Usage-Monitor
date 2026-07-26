import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { HistoryFilters } from './HistoryFilters'
import type { ProfileStatus } from '../../types/usage'

const profiles: ProfileStatus[] = [
  {
    provider: 'claude',
    profile_id: 'p1',
    profile_key: 'claude:p1',
    label: 'default',
    friendly_name: null,
    sanitized_source: '~/.claude',
    discovery_source: 'default',
    is_active: true,
    is_authenticated: null,
    last_refresh_utc: null,
    last_success_utc: null,
    last_error: null,
    is_stale: false,
    executable_found: true,
  },
]

describe('HistoryFilters', () => {
  it('renders all range buttons and marks the active one', () => {
    render(
      <HistoryFilters
        profiles={profiles}
        selectedProfileKey={null}
        onSelectProfile={vi.fn()}
        selectedWindowId={null}
        onSelectWindow={vi.fn()}
        windowOptions={['five_hour']}
        range="7d"
        onSelectRange={vi.fn()}
      />
    )
    const active = screen.getByRole('button', { name: '7d' })
    expect(active).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Today' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onSelectRange when a different range is clicked', () => {
    const onSelectRange = vi.fn()
    render(
      <HistoryFilters
        profiles={profiles}
        selectedProfileKey={null}
        onSelectProfile={vi.fn()}
        selectedWindowId={null}
        onSelectWindow={vi.fn()}
        windowOptions={[]}
        range="7d"
        onSelectRange={onSelectRange}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: '30d' }))
    expect(onSelectRange).toHaveBeenCalledWith('30d')
  })

  it('calls onSelectProfile when a profile is chosen', () => {
    const onSelectProfile = vi.fn()
    render(
      <HistoryFilters
        profiles={profiles}
        selectedProfileKey={null}
        onSelectProfile={onSelectProfile}
        selectedWindowId={null}
        onSelectWindow={vi.fn()}
        windowOptions={[]}
        range="7d"
        onSelectRange={vi.fn()}
      />
    )
    fireEvent.change(screen.getByLabelText(/profile/i), { target: { value: 'claude:p1' } })
    expect(onSelectProfile).toHaveBeenCalledWith('claude:p1')
  })
})
