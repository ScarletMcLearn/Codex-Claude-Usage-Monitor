import clsx from 'clsx'
import { levelForPercent } from '../../types/usage'
import type { DataQuality } from '../../types/usage'

const LEVEL_META = {
  normal: { label: 'Normal', icon: '●', bar: 'bg-emerald-500' },
  moderate: { label: 'Moderate', icon: '▲', bar: 'bg-amber-400' },
  high: { label: 'High', icon: '▲▲', bar: 'bg-orange-500' },
  critical: { label: 'Critical', icon: '⚠', bar: 'bg-red-500' },
  exhausted: { label: 'Exhausted', icon: '⛔', bar: 'bg-red-700' },
  unknown: { label: 'Unknown', icon: '?', bar: 'bg-slate-300 dark:bg-slate-600' },
} as const

export function UsageBar({
  usedPercent,
  quality,
  unavailableReason,
  label,
}: {
  usedPercent: number | null
  quality: DataQuality
  unavailableReason?: string | null
  label?: string
}) {
  const level = levelForPercent(usedPercent, quality)
  const meta = LEVEL_META[level]
  const width = usedPercent === null ? 0 : Math.min(100, Math.max(0, usedPercent))

  return (
    <div data-testid="usage-bar" data-level={level}>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="font-medium text-slate-700 dark:text-slate-200">{label}</span>
        <span className="flex items-center gap-1 text-slate-600 dark:text-slate-300">
          <span aria-hidden="true">{meta.icon}</span>
          <span>{meta.label}</span>
          <span className="font-semibold">
            {usedPercent === null ? '—' : `${usedPercent.toFixed(0)}%`}
          </span>
        </span>
      </div>
      <div
        className="h-2.5 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden"
        role="progressbar"
        aria-valuenow={usedPercent ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label ?? 'Usage'}: ${meta.label}${
          usedPercent === null ? '' : `, ${usedPercent.toFixed(0)}%`
        }`}
      >
        <div
          className={clsx('h-full rounded-full transition-all', meta.bar)}
          style={{ width: `${width}%` }}
        />
      </div>
      {quality === 'unavailable' && unavailableReason && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{unavailableReason}</p>
      )}
    </div>
  )
}
