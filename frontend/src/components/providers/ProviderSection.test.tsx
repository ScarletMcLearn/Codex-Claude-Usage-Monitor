import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProviderSection } from './ProviderSection'

describe('ProviderSection', () => {
  it('shows an empty state when no profiles are discovered for the provider', () => {
    render(
      <ProviderSection
        provider="codex"
        title="Codex"
        profiles={[]}
        limitsByProfile={{}}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
        refreshingKey={null}
      />
    )
    expect(screen.getByText('No Codex profiles discovered')).toBeInTheDocument()
  })

  it('has an accessible section landmark labeled by its heading', () => {
    render(
      <ProviderSection
        provider="claude"
        title="Claude Code"
        profiles={[]}
        limitsByProfile={{}}
        displayTimeZone="Asia/Dhaka"
        onRefresh={vi.fn()}
        onOpenDiagnostics={vi.fn()}
        refreshingKey={null}
      />
    )
    expect(screen.getByRole('region', { name: 'Claude Code' })).toBeInTheDocument()
  })
})
