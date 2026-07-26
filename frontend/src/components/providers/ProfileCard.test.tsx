import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ProfileCard } from './ProfileCard'
import type { ProfileStatus, UsageLimit } from '../../types/usage'

const profile: ProfileStatus = {
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
}

const limits: UsageLimit[] = [
  {
    provider: 'claude',
    profile_id: 'p1',
    window_id: 'five_hour',
    window_label: '5-hour',
    window_duration_minutes: null,
    used_percent: 42,
    used_units: null,
    max_units: null,
    remaining_percent: 58,
    resets_at_utc: new Date(Date.now() + 3_600_000).toISOString(),
    reset_confirmed: false,
    quality: 'verified',
    unavailable_reason: null,
    observed_at_utc: new Date().toISOString(),
    source_detail: {},
  },
]

describe('ProfileCard', () => {
  it('renders profile label, sanitized path, and usage bars', () => {
    render(
      <ProfileCard
        profile={profile}
        limits={limits}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByText('default')).toBeInTheDocument()
    expect(screen.getByText('~/.claude')).toBeInTheDocument()
    expect(screen.getByText('5-hour')).toBeInTheDocument()
  })

  it('shows "No usage data yet" empty state when limits is empty', () => {
    render(
      <ProfileCard
        profile={profile}
        limits={[]}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByText('No usage data yet.')).toBeInTheDocument()
  })

  it('calls onRefresh with the profile_key when Refresh is clicked', () => {
    const onRefresh = vi.fn()
    render(
      <ProfileCard
        profile={profile}
        limits={limits}
        displayTimeZone="Asia/Dhaka"
        onRefresh={onRefresh}
        onOpenDiagnostics={vi.fn()}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /refresh default/i }))
    expect(onRefresh).toHaveBeenCalledWith('claude:p1')
  })

  it('calls onOpenDiagnostics with the profile_key when Diagnostics is clicked', () => {
    const onOpenDiagnostics = vi.fn()
    render(
      <ProfileCard
        profile={profile}
        limits={limits}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={onOpenDiagnostics}
      />
    )
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(onOpenDiagnostics).toHaveBeenCalledWith('claude:p1')
  })

  it('shows last error text when present', () => {
    render(
      <ProfileCard
        profile={{ ...profile, last_error: 'Refresh failed: timeout' }}
        limits={limits}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByText('Refresh failed: timeout')).toBeInTheDocument()
  })
})
