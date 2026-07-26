export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center"
      data-testid="empty-state"
    >
      <p className="font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {description && (
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-prose">{description}</p>
      )}
      {action}
    </div>
  )
}
