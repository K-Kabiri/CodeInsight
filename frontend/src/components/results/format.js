/**
 * Formatting helpers for the results screens. Kept in one module so
 * every card/table renders numbers, timestamps and line ranges the
 * same way, and tests can pin the exact strings.
 */

// A metric value with its unit. Percent metrics (Duplication) render
// with one decimal + '%'; integers stay integers; everything else
// rounds to two decimals. A null value (not_applicable, or a metric
// that could not claim a scalar) renders as an em dash.
export function formatMetricValue(value, unit) {
  if (value === null || value === undefined) return '—'
  if (unit === 'percent') return `${value.toFixed(1)}%`
  if (Number.isInteger(value)) return String(value)
  return value.toFixed(2)
}

// Execution time in seconds: sub-second runs render in milliseconds,
// longer runs in seconds with two decimals.
export function formatExecutionTime(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  return `${seconds.toFixed(2)}s`
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

// A long, human date (e.g. "August 1, 2026") used for membership
// dates on the dashboard profile box and the profile screen.
export function formatLongDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

// A finding's location: file:start–end for the explainable-detail
// convention (smells), file:line for violation records.
export function formatFindingLocation(record) {
  const file = record.file ?? ''
  if (record.lineno !== undefined && record.lineno !== null) {
    const endline =
      record.endline !== undefined && record.endline !== null
        ? `–${record.endline}`
        : ''
    return `${file}:${record.lineno}${endline}`
  }
  if (record.line !== undefined && record.line !== null) {
    return `${file}:${record.line}`
  }
  return file || '—'
}
