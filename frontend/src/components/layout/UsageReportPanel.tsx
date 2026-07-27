import type { UsageReport } from '../../types/usage'
import { StatusBadge } from '../common/StatusBadge'

export function UsageReportPanel({
  report,
  error,
  onClose,
}: {
  report: UsageReport | null
  error: string | null
  onClose: () => void
}) {
  if (!report && !error) return null

  return (
    <section
      className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 space-y-3"
      aria-labelledby="usage-report-heading"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="usage-report-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            Usage Report
          </h2>
          {report && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Checked {report.profiles_checked} profile(s) at {report.generated_at_utc}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700"
          aria-label="Close usage report"
        >
          Close
        </button>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {report && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                <th className="py-2 pr-3">Profile</th>
                <th className="py-2 pr-3">Source</th>
                <th className="py-2 pr-3">Window</th>
                <th className="py-2 pr-3">Used</th>
                <th className="py-2 pr-3">Quality</th>
                <th className="py-2 pr-3">Message</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.flatMap((row) => {
                if (row.limits.length === 0) {
                  return [
                    <tr key={row.profile_key} className="border-t border-slate-100 dark:border-slate-700">
                      <td className="py-2 pr-3">{row.provider} / {row.label}</td>
                      <td className="py-2 pr-3">{row.source}</td>
                      <td className="py-2 pr-3">Usage</td>
                      <td className="py-2 pr-3">-</td>
                      <td className="py-2 pr-3">failed</td>
                      <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">{row.message}</td>
                    </tr>,
                  ]
                }
                return row.limits.map((limit) => (
                  <tr key={`${row.profile_key}:${limit.window_id}`} className="border-t border-slate-100 dark:border-slate-700">
                    <td className="py-2 pr-3">{row.provider} / {row.label}</td>
                    <td className="py-2 pr-3">{row.source}</td>
                    <td className="py-2 pr-3">{limit.window_label}</td>
                    <td className="py-2 pr-3">{limit.used_percent === null ? '-' : `${limit.used_percent.toFixed(0)}%`}</td>
                    <td className="py-2 pr-3"><StatusBadge quality={limit.quality} /></td>
                    <td className="py-2 pr-3 text-slate-500 dark:text-slate-400">
                      {limit.unavailable_reason ?? row.message}
                    </td>
                  </tr>
                ))
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
