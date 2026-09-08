import {
  Alert,
  Box,
  Button,
  CircularProgress,
  LinearProgress,
  Paper,
  Typography,
} from '@mui/material'
import { Link, useParams } from 'react-router-dom'

import { extractErrorMessage, isNotFound } from '../api/errors'
import {
  useAiReport,
  useAnalysis,
  useGenerateAiReport,
  useMetrics,
} from '../api/queries'
import { StatusChip } from '../components/StatusChip'
import {
  AiMetricBox,
  AiSummaryBox,
  AiUnavailableBox,
} from '../components/results/AiReport'
import { MetricCard } from '../components/results/MetricCard'
import { MetricDetail } from '../components/results/MetricDetail'
import { formatDateTime } from '../components/results/format'

/**
 * Analysis results (ticket 05, user stories 13–20): the detail screen
 * polls automatically while the Analysis is PENDING/RUNNING
 * (refetchInterval in useAnalysis) and stops at COMPLETED/FAILED.
 * Once complete, every selected metric renders as a result card
 * (value, unit, status, execution time) plus its rich detail view —
 * findings, tables, cycles — with not_applicable/partial reasons
 * shown gracefully instead of pretend numbers.
 *
 * AI report (ai-report ticket 05): when the run was created with
 * `ai_requested`, a completed Analysis also shows its stored AI
 * report — an overall summary box at the top and, under each metric's
 * detail section, that metric's explanation + suggestions. The AI
 * content sits around the real numbers and never hides them; a
 * missing report (generation failed during the run) shows a readable
 * "AI report unavailable" state with a retry action.
 */
export default function AnalysisDetailPage() {
  const { id } = useParams()
  const analysisQuery = useAnalysis(id)
  const metricsQuery = useMetrics()

  // The report is fetched only once the run is COMPLETED and asked
  // for AI (the report row is written before that transition, so no
  // extra polling is needed — see useAiReport).
  const aiEnabled =
    analysisQuery.data?.status === 'COMPLETED' &&
    analysisQuery.data?.ai_requested === true
  const reportQuery = useAiReport(id, aiEnabled)
  const generateReport = useGenerateAiReport(id)

  const analysis = analysisQuery.data
  const catalogByName = new Map(
    (metricsQuery.data ?? []).map((entry) => [entry.name, entry]),
  )

  if (analysisQuery.isLoading) {
    return (
      <Box sx={{ display: 'grid', placeItems: 'center', py: 10 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (analysisQuery.isError) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          {isNotFound(analysisQuery.error)
            ? 'Analysis not found'
            : 'Something went wrong'}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {isNotFound(analysisQuery.error)
            ? "It doesn't exist or you don't have access to it."
            : extractErrorMessage(analysisQuery.error)}
        </Typography>
        <Button component={Link} to="/analyses">
          Back to analyses
        </Button>
      </Box>
    )
  }

  const inFlight = analysis.status === 'PENDING' || analysis.status === 'RUNNING'
  const failed = analysis.status === 'FAILED'
  const completedMetrics = analysis.metrics ?? []

  // AI area state: only for COMPLETED runs that asked for AI; the
  // report query must have settled (success → report/null, error →
  // unavailable with the read-back reason).
  const aiWanted = Boolean(analysis.ai_requested) && !inFlight && !failed
  const aiResolved = reportQuery.isSuccess || reportQuery.isError
  const aiReport = reportQuery.data || null
  const aiActionError = generateReport.isError
    ? extractErrorMessage(generateReport.error)
    : null

  return (
    <Box sx={{ overflowX: 'hidden' }}>
      <Button component={Link} to="/analyses" sx={{ mb: 2 }}>
        ← Back to analyses
      </Button>

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
          flexWrap: 'wrap',
          mb: 1,
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Analysis #{analysis.id}
          </Typography>
          <Typography color="text.secondary" variant="body2">
            Created {formatDateTime(analysis.created_at)}
            {analysis.started_at &&
              ` · Started ${formatDateTime(analysis.started_at)}`}
            {analysis.finished_at &&
              ` · Finished ${formatDateTime(analysis.finished_at)}`}
          </Typography>
        </Box>
        <StatusChip status={analysis.status} />
      </Box>

      {inFlight && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            The analysis is still running — results refresh
            automatically.
          </Typography>
        </Box>
      )}

      {failed && (
        <Alert severity="error" sx={{ mb: 3 }}>
          This analysis failed. Each metric below shows its own error
          message where one was reported.
        </Alert>
      )}

      {aiWanted && aiResolved &&
        (aiReport ? (
          <AiSummaryBox
            report={aiReport}
            generating={generateReport.isPending}
            error={aiActionError}
            onRegenerate={() => generateReport.mutate()}
          />
        ) : (
          <AiUnavailableBox
            reason={
              reportQuery.isError
                ? extractErrorMessage(reportQuery.error)
                : null
            }
            retrying={generateReport.isPending}
            error={aiActionError}
            onRetry={() => generateReport.mutate()}
          />
        ))}

      {completedMetrics.length > 0 && (
        <Box
          sx={{
            display: 'grid',
            // minmax(0, 1fr): card columns can never exceed the page
            // width, so long text wraps and grows a card's height
            // instead of widening the grid (no horizontal scroll).
            gridTemplateColumns: {
              xs: 'repeat(2, minmax(0, 1fr))',
              md: 'repeat(3, minmax(0, 1fr))',
              lg: 'repeat(4, minmax(0, 1fr))',
            },
            gap: 2,
            mb: 3,
          }}
        >
          {completedMetrics.map((metric) => (
            <MetricCard
              key={metric.name}
              metric={metric}
              catalogEntry={catalogByName.get(metric.name)}
            />
          ))}
        </Box>
      )}

      {!inFlight && !failed && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {completedMetrics.map((metric) => (
            <Paper
              key={metric.name}
              elevation={0}
              sx={{
                p: 2.5,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
                {metric.display_name}
              </Typography>
              <MetricDetail metric={metric} />
              {aiWanted && aiReport && (
                <AiMetricBox
                  content={aiReport.metric_content?.[metric.name]}
                />
              )}
            </Paper>
          ))}
        </Box>
      )}
    </Box>
  )
}
