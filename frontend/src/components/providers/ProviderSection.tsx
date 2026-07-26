import type { ProfileStatus, UsageLimit } from '../../types/usage'
import { ProfileCard } from './ProfileCard'
import { EmptyState } from '../common/EmptyState'

export function ProviderSection({
  provider,
  title,
  profiles,
  limitsByProfile,
  displayTimeZone,
  onRefresh,
  onOpenDiagnostics,
  refreshingKey,
}: {
  provider: 'claude' | 'codex'
  title: string
  profiles: ProfileStatus[]
  limitsByProfile: Record<string, UsageLimit[]>
  displayTimeZone: string
  onRefresh: (profileKey: string) => void
  onOpenDiagnostics: (profileKey: string) => void
  refreshingKey: string | null
}) {
  return (
    <section aria-labelledby={`section-${provider}`} className="space-y-3">
      <h2
        id={`section-${provider}`}
        className={
          provider === 'claude'
            ? 'text-lg font-semibold text-orange-700 dark:text-orange-400'
            : 'text-lg font-semibold text-teal-700 dark:text-teal-400'
        }
      >
        {title}
      </h2>
      {profiles.length === 0 ? (
        <EmptyState
          title={`No ${title} profiles discovered`}
          description="Check that the CLI is installed and a config directory exists for this provider."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {profiles.map((profile) => (
            <ProfileCard
              key={profile.profile_key}
              profile={profile}
              limits={limitsByProfile[profile.profile_key] ?? []}
              displayTimeZone={displayTimeZone}
              onRefresh={onRefresh}
              onOpenDiagnostics={onOpenDiagnostics}
              isRefreshing={refreshingKey === profile.profile_key}
            />
          ))}
        </div>
      )}
    </section>
  )
}
