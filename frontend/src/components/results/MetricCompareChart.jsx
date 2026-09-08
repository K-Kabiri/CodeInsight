import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatMetricValue } from './format'

/**
 * One headline metric's comparison chart (ticket 06): two bars —
 * baseline vs compared — so the user sees the change at a glance.
 * recharts renders the SVG; the theme's primary/secondary palette
 * colors the bars. A null side (e.g. cyclic dependencies
 * not_applicable on a single-file input) renders as an empty slot
 * instead of a fake bar.
 */

const BAR_FILLS = ['#6c8cff', '#5ee6c8'] // theme primary / secondary

export function MetricCompareChart({
  displayName,
  unit,
  baseline,
  compared,
}) {
  const data = [
    { name: baseline.label, value: baseline.value ?? null },
    { name: compared.label, value: compared.value ?? null },
  ]

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a3142" />
        <XAxis
          dataKey="name"
          stroke="#8b93a7"
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#8b93a7"
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => formatMetricValue(value, unit)}
        />
        <Tooltip
          formatter={(value) => [
            formatMetricValue(value, unit),
            displayName,
          ]}
          contentStyle={{
            background: '#161a23',
            border: '1px solid #2a3142',
            borderRadius: 8,
          }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
          {data.map((entry, index) => (
            <Cell key={entry.name} fill={BAR_FILLS[index]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
