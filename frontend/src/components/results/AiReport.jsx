import {
  Alert,
  Box,
  Button,
  Paper,
  Typography,
} from '@mui/material'

import { formatDateTime } from './format'

/**
 * AI report rendering (ai-report ticket 05). The report never hides
 * the real numbers: these boxes sit *around* the metric cards and
 * detail sections and add plain-language content on top of them.
 * Text is intentionally simple prose + suggestion bullets so the
 * tests pin content, not chrome.
 */

/**
 * The overall summary box shown at the top of a COMPLETED Analysis's
 * results when a report exists. The "Regenerate report" action
 * re-POSTs the whole report; a failed regeneration surfaces inline
 * while the previously stored summary stays visible.
 */
export function AiSummaryBox({ report, onRegenerate, generating, error }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        mb: 3,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
          mb: 1,
        }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          AI summary
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={onRegenerate}
          disabled={generating}
        >
          {generating ? 'Generating…' : 'Regenerate report'}
        </Button>
      </Box>

      <Typography variant="body1" sx={{ overflowWrap: 'anywhere' }}>
        {report.summary}
      </Typography>

      {(report.model_name || report.generated_at) && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            mt: 1,
            display: 'block',
            overflowWrap: 'anywhere',
          }}
        >
          {report.model_name && `AI · ${report.model_name}`}
          {report.generated_at &&
            ` · ${formatDateTime(report.generated_at)}`}
        </Typography>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }}>
          {error}
        </Alert>
      )}
    </Paper>
  )
}

/**
 * The "AI report unavailable" state: `ai_requested` was on but no
 * report exists (generation failed during the run, or the read-back
 * errored). Offers the retry action that POSTs a fresh generation.
 * The metric results below are always unaffected.
 */
export function AiUnavailableBox({ reason, onRetry, retrying, error }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        mb: 3,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
        AI report unavailable
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 1.5, overflowWrap: 'anywhere' }}
      >
        {reason ??
          'This analysis asked for AI explanations, but no report was generated — the LLM call may have failed or no API key was configured. Your metric results are unaffected.'}
      </Typography>
      <Button
        size="small"
        variant="outlined"
        onClick={onRetry}
        disabled={retrying}
      >
        {retrying ? 'Generating…' : 'Retry'}
      </Button>

      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }}>
          {error}
        </Alert>
      )}
    </Paper>
  )
}

/**
 * One metric's explanation + suggestions, rendered under that
 * metric's detail section. Returns null when the report carries no
 * entry for the metric (the section then shows only the real
 * numbers, unchanged).
 */
export function AiMetricBox({ content }) {
  if (!content) return null

  const suggestions = content.suggestions ?? []

  return (
    <Box
      sx={{
        mt: 2,
        pt: 2,
        borderTop: '1px dashed',
        borderColor: 'divider',
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
        AI explanation
      </Typography>
      <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>
        {content.explanation}
      </Typography>

      {suggestions.length > 0 && (
        <>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mt: 1 }}
          >
            Suggestions
          </Typography>
          <Box component="ul" sx={{ m: 0, mt: 0.25, pl: 2.5 }}>
            {suggestions.map((suggestion) => (
              <Typography
                component="li"
                variant="body2"
                key={suggestion}
                sx={{ overflowWrap: 'anywhere' }}
              >
                {suggestion}
              </Typography>
            ))}
          </Box>
        </>
      )}
    </Box>
  )
}
