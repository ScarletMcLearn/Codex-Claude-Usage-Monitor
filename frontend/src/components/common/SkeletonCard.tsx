export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      className="animate-pulse rounded-lg border border-slate-200 dark:border-slate-700 p-4 space-y-3"
      data-testid="skeleton-card"
      role="status"
      aria-label="Loading"
    >
      <div className="h-4 w-1/3 rounded bg-slate-200 dark:bg-slate-700" />
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 w-full rounded bg-slate-200 dark:bg-slate-700" />
      ))}
    </div>
  )
}
