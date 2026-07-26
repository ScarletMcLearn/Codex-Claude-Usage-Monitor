import { useEffect, useState } from 'react'

function formatDuration(ms: number): string {
  if (ms <= 0) return 'due now'
  const totalMinutes = Math.floor(ms / 60_000)
  const days = Math.floor(totalMinutes / (60 * 24))
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60)
  const minutes = totalMinutes % 60
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0 || days > 0) parts.push(`${hours}h`)
  parts.push(`${minutes}m`)
  return parts.join(' ')
}

/** Renders a live countdown to `targetIso`, and the local (Asia/Dhaka by
 * default, browser-local otherwise) wall-clock time. Never fabricates a
 * value: if targetIso is null, shows an explicit "Unknown" state. */
export function CountdownTimer({
  targetIso,
  displayTimeZone,
}: {
  targetIso: string | null
  displayTimeZone?: string
}) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!targetIso) return
    const id = setInterval(() => setNow(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [targetIso])

  if (!targetIso) {
    return (
      <span className="text-slate-500 dark:text-slate-400" data-testid="countdown-unknown">
        Unknown
      </span>
    )
  }

  const target = new Date(targetIso).getTime()
  const remaining = target - now

  let localTime: string
  try {
    localTime = new Intl.DateTimeFormat(undefined, {
      timeZone: displayTimeZone,
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(target)
  } catch {
    localTime = new Date(target).toLocaleString()
  }

  return (
    <span title={localTime} data-testid="countdown">
      {formatDuration(remaining)}{' '}
      <span className="text-slate-500 dark:text-slate-400 text-xs">({localTime})</span>
    </span>
  )
}
