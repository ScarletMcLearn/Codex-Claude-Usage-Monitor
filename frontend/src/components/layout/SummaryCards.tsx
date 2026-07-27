import type { Summary } from '../../types/usage'
import { CountdownTimer } from '../common/CountdownTimer'

function Card({
  label,
  value,
  tone,
  className,
  valueClassName,
}: {
  label: string
  value: React.ReactNode
  tone?: string
  className?: string
  valueClassName?: string
}) {
  return (
    <div
      className={`rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3 ${className ?? ''}`}
    >
      <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
      <p
        className={`${valueClassName ?? 'text-2xl'} font-semibold ${tone ?? 'text-slate-900 dark:text-slate-50'}`}
      >
        {value}
      </p>
    </div>
  )
}

export function SummaryCards({
  summary,
  displayTimeZone,
}: {
  summary: Summary
  displayTimeZone: string
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3" data-testid="summary-cards">
      <Card label="Total profiles" value={summary.total_profiles} />
      <Card label="Queried OK" value={summary.queried_successfully} />
      <Card
        label="Need auth"
        value={summary.need_auth}
        tone={summary.need_auth > 0 ? 'text-amber-600 dark:text-amber-400' : undefined}
      />
      <Card
        label="Limits > 80%"
        value={summary.over_80_percent}
        tone={summary.over_80_percent > 0 ? 'text-orange-600 dark:text-orange-400' : undefined}
      />
      <Card
        label="Limits > 95%"
        value={summary.over_95_percent}
        tone={summary.over_95_percent > 0 ? 'text-red-600 dark:text-red-400' : undefined}
      />
      <Card
        label="Next reset"
        value={<CountdownTimer targetIso={summary.next_reset_utc} displayTimeZone={displayTimeZone} />}
        className="col-span-2 md:col-span-2"
        valueClassName="text-3xl leading-tight"
      />
      <Card
        label="Stale / failed"
        value={summary.stale_or_failed}
        tone={summary.stale_or_failed > 0 ? 'text-amber-600 dark:text-amber-400' : undefined}
      />
    </div>
  )
}
