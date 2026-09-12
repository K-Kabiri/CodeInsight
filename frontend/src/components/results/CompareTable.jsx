import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'

import { buildCompareRows, deltaOf } from './compare'
import { metricValueLabel } from './applicability'
import { formatMetricValue } from './format'

/**
 * The comparison delta table (ticket 06): every metric both versions
 * completed, side by side with the v2 − v1 delta. The delta is
 * colored by whether the change is an improvement for that metric
 * (the catalog's higher_is_better decides the direction): green =
 * improved, red = worse, gray = unchanged. Values use the same
 * formatting helpers as every other results screen — a metric that is
 * not applicable to the input says so instead of showing an
 * unexplained dash (ADR-0001).
 */

function DeltaCell({ delta, unit }) {
  if (!delta) {
    return <TableCell>—</TableCell>
  }

  const arrow = delta.improved ? '▲' : '▼'
  const color = delta.equal
    ? 'text.secondary'
    : delta.improved
      ? 'success.main'
      : 'error.main'

  return (
    <TableCell sx={{ color }}>
      {delta.equal ? (
        '±0'
      ) : (
        <>
          {arrow} {formatMetricValue(Math.abs(delta.delta), unit)}
        </>
      )}
    </TableCell>
  )
}

export function CompareTable({ baseline, compared, catalogByName }) {
  const rows = buildCompareRows(baseline, compared)

  if (rows.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No metric was completed on both versions — run an Analysis with
        the same metrics on each version to compare them.
      </Typography>
    )
  }

  return (
    <TableContainer
      component={Paper}
      elevation={0}
      variant="outlined"
      sx={{ borderColor: 'divider' }}
    >
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 700 }}>Metric</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Baseline</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Compared</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Δ</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => {
            const catalogEntry = catalogByName?.get(row.name)
            const unit = catalogEntry?.unit ?? ''
            const higherIsBetter = catalogEntry?.higher_is_better === true
            const delta = deltaOf(
              row.baselineValue,
              row.comparedValue,
              higherIsBetter,
            )

            return (
              <TableRow key={row.name} hover>
                <TableCell sx={{ fontWeight: 600 }}>
                  {catalogEntry?.display_name ?? row.name}
                </TableCell>
                <TableCell>
                  {metricValueLabel(
                    row.baselineMetric,
                    row.baselineValue,
                    unit,
                  )}
                </TableCell>
                <TableCell>
                  {metricValueLabel(
                    row.comparedMetric,
                    row.comparedValue,
                    unit,
                  )}
                </TableCell>
                <DeltaCell delta={delta} unit={unit} />
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
