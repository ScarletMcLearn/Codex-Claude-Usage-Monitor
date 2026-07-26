import {
  Line,
  LineChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'
import type { HistoryRow } from '../../types/usage'
import { EmptyState } from '../common/EmptyState'

interface ChartPoint {
  t: number
  timeLabel: string
  used_percent: number | null
  quality: HistoryRow['quality']
  isResetBoundary: boolean
}

function toChartData(rows: HistoryRow[]): ChartPoint[] {
  return rows.map((row) => ({
    t: new Date(row.observed_at_utc).getTime(),
    timeLabel: new Date(row.observed_at_utc).toLocaleString(),
    // Only plot a numeric value when quality is trustworthy enough to chart;
    // unavailable readings become gaps (null), never interpolated as 0.
    used_percent: row.quality === 'unavailable' ? null : row.used_percent,
    quality: row.quality,
    isResetBoundary: Boolean(row.is_reset_boundary),
  }))
}

export function HistoryChart({ rows }: { rows: HistoryRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No history yet"
        description="Once refreshes start recording snapshots, usage over time will appear here."
      />
    )
  }

  const data = toChartData(rows)
  const resetBoundaries = data.filter((d) => d.isResetBoundary)

  return (
    <div style={{ width: '100%', height: 320 }} data-testid="history-chart">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-slate-700" />
          <XAxis
            dataKey="t"
            tickFormatter={(t) => new Date(t).toLocaleDateString()}
            type="number"
            domain={['dataMin', 'dataMax']}
            className="text-xs"
          />
          <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} className="text-xs" />
          <Tooltip
            labelFormatter={(t) => new Date(t as number).toLocaleString()}
            formatter={(value) => [value === null || value === undefined ? 'no data' : `${value}%`, 'Used']}
          />
          <Legend />
          {resetBoundaries.map((rb) => (
            <ReferenceLine
              key={rb.t}
              x={rb.t}
              stroke="#f59e0b"
              strokeDasharray="4 4"
              label={{ value: 'reset', position: 'top', fontSize: 10, fill: '#f59e0b' }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="used_percent"
            name="Used %"
            stroke="#0ea5e9"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
