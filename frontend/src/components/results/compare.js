/**
 * Pure helpers for the version-comparison screen (ticket 06):
 * pick a version's newest COMPLETED analysis, extract a comparable
 * scalar for a metric (the headline four read their official summary
 * field from the persisted `detail` so the delta table and the charts
 * always agree), and build the delta rows.
 */

// A version's comparison point: the newest COMPLETED Analysis,
// newest by `finished_at` (falling back to `created_at`). In-flight
// and failed runs are never compared — the detail screen polls those;
// the comparison is a settled snapshot.
export function newestCompleted(analyses) {
  const completed = (analyses ?? []).filter(
    (analysis) => analysis.status === 'COMPLETED',
  )
  if (completed.length === 0) return null

  return [...completed].sort((a, b) => {
    const at = a.finished_at || a.created_at
    const bt = b.finished_at || b.created_at
    return new Date(bt) - new Date(at)
  })[0]
}

// The official summary field per headline metric, read from `detail`
// (the same numbers the detail renderers show): LOC total, average
// complexity, total smells, duplication density. Every other metric
// falls back to the serialized scalar `value`.
const HEADLINE_SCALAR = {
  LOC: (detail) => detail?.totals?.loc,
  CYCLOMATIC: (detail) => detail?.average,
  CODE_SMELLS: (detail) => detail?.totals?.smells,
  DUPLICATION: (detail) => detail?.density,
}

export function comparisonScalar(metric) {
  if (!metric || metric.status !== 'COMPLETED') return null
  const fromDetail = HEADLINE_SCALAR[metric.name]
  const value = fromDetail ? fromDetail(metric.detail) : metric.value
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/**
 * Delta rows for the two sides: one row per metric completed on BOTH
 * sides (a metric a version never ran, or failed, has no comparable
 * outcome — it is simply not a row). Each row carries the scalar
 * values so the table and any chart share one source of truth.
 */
export function buildCompareRows(baseline, compared) {
  const byName = (analysis) =>
    new Map((analysis?.metrics ?? []).map((metric) => [metric.name, metric]))
  const baselineMap = byName(baseline)
  const comparedMap = byName(compared)

  const names = [
    ...new Set([...baselineMap.keys(), ...comparedMap.keys()]),
  ]

  return names
    .map((name) => {
      const baselineMetric = baselineMap.get(name)
      const comparedMetric = comparedMap.get(name)

      if (
        !baselineMetric ||
        !comparedMetric ||
        baselineMetric.status !== 'COMPLETED' ||
        comparedMetric.status !== 'COMPLETED'
      ) {
        return null
      }

      return {
        name,
        baselineMetric,
        comparedMetric,
        baselineValue: comparisonScalar(baselineMetric),
        comparedValue: comparisonScalar(comparedMetric),
      }
    })
    .filter(Boolean)
}

// The v2 - v1 delta plus its direction meaning: improved when the
// change favors higher_is_better (or lower, for the majority of
// metrics), equal when there is no change.
export function deltaOf(baselineValue, comparedValue, higherIsBetter) {
  if (baselineValue === null || comparedValue === null) return null
  const delta = comparedValue - baselineValue
  const equal = delta === 0
  const improved = higherIsBetter ? delta > 0 : delta < 0
  return { delta, equal, improved }
}
