import { Alert } from '@mui/material'

const COMPLETENESS_META = {
  not_applicable: {
    severity: 'info',
    title: 'Not applicable',
  },
  partial: {
    severity: 'warning',
    title: 'Partial results',
  },
}

/**
 * Graceful display for the ADR-0001 completeness contract: a metric
 * that is `not_applicable` (e.g. Cyclic Dependencies on a single
 * file) or `partial` (e.g. Instability on a single file) shows its
 * human-readable reason instead of a pretend number. Renders nothing
 * when the metric is `full` or the detail is missing.
 */
export function CompletenessNote({ detail }) {
  const completeness = detail?.completeness
  const meta = COMPLETENESS_META[completeness]
  if (!meta) return null

  return (
    <Alert
      severity={meta.severity}
      sx={{
        mt: 1,
        // Long reasons wrap inside the alert (growing the note's
        // height) instead of widening the page.
        '& .MuiAlert-message': {
          minWidth: 0,
          overflowWrap: 'anywhere',
        },
      }}
    >
      <strong>{meta.title}:</strong>{' '}
      {detail.reason || 'See the detail payload for why.'}
    </Alert>
  )
}
