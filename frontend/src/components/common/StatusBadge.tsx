import clsx from 'clsx'
import type { DataQuality } from '../../types/usage'

const LABELS: Record<DataQuality, string> = {
  verified: 'Verified',
  derived: 'Derived',
  estimated: 'Estimated',
  stale: 'Stale',
  unavailable: 'Unavailable',
}

const ICONS: Record<DataQuality, string> = {
  verified: '✓', // check
  derived: '≈', // approx
  estimated: '~',
  stale: '⏱', // clock
  unavailable: '—', // em dash
}

const STYLES: Record<DataQuality, string> = {
  verified: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  derived: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  estimated: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
  stale: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  unavailable: 'bg-slate-200 text-slate-700 dark:bg-slate-700/50 dark:text-slate-300',
}

export function StatusBadge({ quality }: { quality: DataQuality }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        STYLES[quality]
      )}
      data-testid="status-badge"
      data-quality={quality}
    >
      <span aria-hidden="true">{ICONS[quality]}</span>
      {LABELS[quality]}
    </span>
  )
}
