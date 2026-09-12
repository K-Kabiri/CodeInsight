import { formatMetricValue } from './format'

/**
 * Metric-level applicability (ADR-0001). An engine can finish its run
 * — the AnalysisMetric row is `COMPLETED` — and still make no numeric
 * claim: on a single-file input Cyclic Dependencies is
 * `not_applicable` (a cycle needs two modules) and Instability is
 * `partial` (Ca cannot be observed, so no I is claimed). The evidence
 * lives in the persisted `detail.completeness` and `detail.reason`.
 *
 * These helpers turn that evidence into one state the results UI can
 * render, so a card never labels such a metric `COMPLETED` beside an
 * unexplained dash — the user must be able to tell "no problem found"
 * apart from "this metric does not apply to this input".
 */

export const NOT_APPLICABLE = 'not_applicable'
export const PARTIAL = 'partial'

// The value outcome: the metric really carries a scalar (a partial
// metric carries a real lower bound, e.g. CBO inside one file).
export const VALUE = 'value'

// A completed run that produced no scalar and left no completeness
// evidence behind (a payload predating this contract).
export const NO_VALUE = 'no_value'

// The completeness an AnalysisMetric's persisted detail carries
// ('full' | 'partial' | 'not_applicable'), or null when there is no
// detail at all (pending, running, failed).
export function metricCompleteness(metric) {
  return metric?.detail?.completeness ?? null
}

function hasScalar(metric) {
  return (
    typeof metric?.value === 'number' && Number.isFinite(metric.value)
  )
}

/**
 * How a metric's result must be presented:
 *
 * - `'value'`          → a real scalar is reported;
 * - `'not_applicable'` → the metric cannot be computed for this input
 *                        (no number exists, and none is invented);
 * - `'partial'`        → the run could not claim a scalar for this
 *                        scope, though it could observe part of the
 *                        metric (Instability on one file);
 * - `'no_value'`       → a completed run with no scalar and no
 *                        completeness evidence;
 * - `'PENDING'` / `'RUNNING'` / `'FAILED'` are returned as-is: those
 *   are run states, not applicability states.
 */
export function metricOutcome(metric) {
  if (!metric) return NO_VALUE
  if (metric.status !== 'COMPLETED') return metric.status
  if (hasScalar(metric)) return VALUE

  const completeness = metricCompleteness(metric)
  if (completeness === NOT_APPLICABLE) return NOT_APPLICABLE
  if (completeness === PARTIAL) return PARTIAL

  return NO_VALUE
}

/**
 * The display status for a metric card: the applicability state when
 * the completed run made no numeric claim, otherwise the run status.
 */
export function metricDisplayStatus(metric) {
  const outcome = metricOutcome(metric)

  if (outcome === NOT_APPLICABLE) return 'NOT_APPLICABLE'
  if (outcome === PARTIAL) return 'PARTIAL'
  if (outcome === NO_VALUE) return 'NO_VALUE'

  return metric?.status ?? 'PENDING'
}

// The engine's own explanation of why the metric carries no scalar
// (written into the persisted detail under the ADR-0001 contract).
export function metricReason(metric) {
  return metric?.detail?.reason ?? null
}

/**
 * The value of one side of a comparison: the formatted scalar, or the
 * words "Not applicable" when the metric cannot be computed for that
 * input. A bare em dash would be indistinguishable from a metric that
 * simply was not run, which is the confusion ADR-0001 forbids.
 */
export function metricValueLabel(metric, value, unit) {
  if (metricOutcome(metric) === NOT_APPLICABLE) return 'Not applicable'
  return formatMetricValue(value, unit)
}
