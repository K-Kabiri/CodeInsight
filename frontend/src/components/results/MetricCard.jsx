import { Box, Paper, Typography } from '@mui/material'

import { StatusChip } from '../StatusChip'
import { formatExecutionTime, formatMetricValue } from './format'

// Per-metric floor (in the metric's own unit) below which the
// "Lower is better" nudge is dropped: the result already sits at the
// good end of that metric's scale. Scales differ per metric — small
// counts, a 0–1 fraction, a percentage — so this is deliberately not
// one global number. Metrics without an entry (LOC, Halstead: large
// totals that never reach a "small" band) default to 0 and keep only
// the zero/FAILED rule.
const DIRECTION_HINT_FLOOR = {
  CODE_SMELLS: 5,
  VIOLATIONS: 5,
  CYCLOMATIC: 5,
  COGNITIVE: 5,
  CBO: 5,
  LCOM: 5,
  DIT: 5,
  INSTABILITY: 0.1, // 0–1 scale
  DUPLICATION: 5, // percent
  CYCLIC: 1, // even a single dependency cycle is noteworthy
}

/**
 * One metric's result card (ticket 05): display name, value + unit,
 * status, and execution time. The unit and direction hint come from
 * the public catalog (the Analysis payload itself carries no unit).
 * A `not_applicable`/`partial` metric renders its reason inline so it
 * is never mistaken for a silent gap.
 *
 * The "Lower is better" nudge only appears next to a result that can
 * actually carry it: a FAILED metric has no value, and a value below
 * the metric's own floor (see DIRECTION_HINT_FLOOR) means the code is
 * already at the good end of that metric's scale — pinning the hint
 * there would be noise. The floor is per metric because the scales
 * differ (small counts vs a 0–1 fraction vs a percentage vs large
 * totals); a metric without an entry keeps the plain zero rule.
 */
export function MetricCard({ metric, catalogEntry }) {
  const unit = catalogEntry?.unit ?? ''
  const value =
    metric.status === 'COMPLETED'
      ? formatMetricValue(metric.value, unit)
      : '…'

  const hintVisible =
    metric.status === 'COMPLETED' &&
    typeof metric.value === 'number' &&
    metric.value > 0 &&
    metric.value >= (DIRECTION_HINT_FLOOR[metric.name] ?? 0) &&
    catalogEntry?.higher_is_better === false

  const running =
    metric.status === 'PENDING' || metric.status === 'RUNNING'

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        minWidth: 0,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 1,
        }}
      >
        <Typography
          variant="subtitle2"
          sx={{ fontWeight: 700, overflowWrap: 'anywhere', minWidth: 0 }}
        >
          {metric.display_name}
        </Typography>
        <StatusChip status={metric.status} />
      </Box>

      <Typography variant="h4" sx={{ fontWeight: 700 }}>
        {value}
        {metric.status === 'COMPLETED' && unit && (
          <Typography
            component="span"
            variant="body2"
            color="text.secondary"
            sx={{ ml: 0.5 }}
          >
            {unit}
          </Typography>
        )}
      </Typography>

      {(metric.status === 'COMPLETED' || running) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {metric.status === 'COMPLETED'
              ? `${formatExecutionTime(metric.execution_time)} execution`
              : 'Running…'}
          </Typography>
          {hintVisible && (
            <Typography variant="caption" color="text.secondary">
              Lower is better
            </Typography>
          )}
        </Box>
      )}

      {metric.error_message && (
        <Typography
          variant="body2"
          color="error.main"
          sx={{ overflowWrap: 'anywhere' }}
        >
          {metric.error_message}
        </Typography>
      )}
    </Paper>
  )
}
