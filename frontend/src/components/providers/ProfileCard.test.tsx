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
    expect(screen.getByText('Used')).toBeInTheDocument()
    expect(screen.getByTestId('used-percent')).toHaveTextContent('42%')
    expect(screen.getByTestId('remaining-percent')).toHaveTextContent('58%')
    expect(screen.getByTestId('reset-countdown')).not.toHaveTextContent('Unknown')
  })

  it('shows empty state when limits is empty', () => {
    render(
      <ProfileCard
        profile={profile}
        limits={[]}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByText(/No usage snapshots captured yet/i)).toBeInTheDocument()
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

  it('shows unknown metrics without fabricating zeroes', () => {
    render(
      <ProfileCard
        profile={profile}
        limits={[
          {
            ...limits[0],
            used_percent: null,
            remaining_percent: null,
            resets_at_utc: null,
            quality: 'unavailable',
            unavailable_reason: 'No usage data',
          },
        ]}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByTestId('used-percent')).toHaveTextContent('—')
    expect(screen.getByTestId('remaining-percent')).toHaveTextContent('—')
    expect(screen.getByTestId('reset-countdown')).toHaveTextContent('Unknown')
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('renders Free-AI local counts without blank quota fields', () => {
    render(
      <ProfileCard
        profile={{
          ...profile,
          provider: 'free_ai',
          profile_id: 'free-ai',
          profile_key: 'free_ai:free-ai',
          label: 'Free-AI',
          sanitized_source: 'H:\\Projects\\AI\\Free-AI\\Free-AI',
        }}
        limits={[
          {
            ...limits[0],
            provider: 'free_ai',
            profile_id: 'free-ai',
            window_id: 'gemini_gemini_3_6_flash',
            window_label: 'Gemini / gemini-3.6-flash',
            used_percent: null,
            used_units: 4,
            max_units: null,
            remaining_percent: null,
            resets_at_utc: null,
            source_detail: { source: 'free_ai_local_router_logs' },
          },
        ]}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByText('Requests')).toBeInTheDocument()
    expect(screen.getByTestId('used-percent')).toHaveTextContent('4 req')
    expect(screen.getByText('Quota')).toBeInTheDocument()
    expect(screen.getByTestId('remaining-percent')).toHaveTextContent('Not probed')
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByTestId('reset-countdown')).toHaveTextContent('Local logs')
  })

  it('shows stale values with stale reason', () => {
    render(
      <ProfileCard
        profile={profile}
        limits={[
          {
            ...limits[0],
            quality: 'stale',
            unavailable_reason: 'Last observed 1h ago.',
          },
        ]}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
      />
    )
    expect(screen.getByTestId('used-percent')).toHaveTextContent('42%')
    expect(screen.getByText('Stale')).toBeInTheDocument()
    expect(screen.getByText('Last observed 1h ago.')).toBeInTheDocument()
  })
})
