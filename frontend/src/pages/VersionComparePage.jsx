import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { extractErrorMessage, isNotFound } from '../api/errors'
import {
  useMetrics,
  useProject,
  useVersionAnalyses,
  useVersions,
} from '../api/queries'
import { CompareTable } from '../components/results/CompareTable'
import {
  comparisonScalar,
  newestCompleted,
} from '../components/results/compare'
import { MetricCompareChart } from '../components/results/MetricCompareChart'
import { metricValueLabel } from '../components/results/applicability'

// The headline metrics the ticket names for charts. Each reads its
// scalar from the persisted detail (see comparisonScalar), so the
// chart and the delta table always agree.
const HEADLINE_METRICS = [
  'LOC',
  'CYCLOMATIC',
  'CODE_SMELLS',
  'DUPLICATION',
]

/**
 * Version comparison (ticket 06, user story 21–22): pick two versions
 * of a project and see their newest COMPLETED Analysis outcomes side
 * by side — the full metric delta table plus charts for the headline
 * metrics (LOC, complexity, smells, duplication). Each side fetches
 * its version's Analyses via ?project_version=<id> and uses the newest
 * completed run; versions with no completed Analysis get their own
 * empty state instead of a fabricated number.
 */
export default function VersionComparePage() {
  const { id } = useParams()
  const projectQuery = useProject(id)
  const versionsQuery = useVersions(id)
  const metricsQuery = useMetrics()

  const versions = versionsQuery.data ?? []
  const [baselineId, setBaselineId] = useState('')
  const [comparedId, setComparedId] = useState('')

  // Preselect the two newest versions until the user picks others.
  const effectiveBaselineId =
    baselineId || (versions[0] ? String(versions[0].id) : '')
  const effectiveComparedId =
    comparedId || (versions[1] ? String(versions[1].id) : '')

  const baselineVersion = versions.find(
    (version) => String(version.id) === String(effectiveBaselineId),
  )
  const comparedVersion = versions.find(
    (version) => String(version.id) === String(effectiveComparedId),
  )

  const baselineAnalyses = useVersionAnalyses(effectiveBaselineId)
  const comparedAnalyses = useVersionAnalyses(effectiveComparedId)

  const baselineOutcome = newestCompleted(baselineAnalyses.data)
  const comparedOutcome = newestCompleted(comparedAnalyses.data)

  const catalogByName = useMemo(
    () =>
      new Map((metricsQuery.data ?? []).map((entry) => [entry.name, entry])),
    [metricsQuery.data],
  )

  if (projectQuery.isLoading || versionsQuery.isLoading) {
    return (
      <Box sx={{ display: 'grid', placeItems: 'center', py: 10 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (projectQuery.isError) {
    return (
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          {isNotFound(projectQuery.error)
            ? 'Project not found'
            : 'Something went wrong'}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {isNotFound(projectQuery.error)
            ? "It doesn't exist or you don't have access to it."
            : extractErrorMessage(projectQuery.error)}
        </Typography>
        <Button component={Link} to="/">
          Back to dashboard
        </Button>
      </Box>
    )
  }

  const project = projectQuery.data

  if (versions.length < 2) {
    return (
      <Box>
        <Button component={Link} to={`/projects/${id}`} sx={{ mb: 2 }}>
          ← Back to project
        </Button>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
          {project.name} — Compare versions
        </Typography>
        <Paper
          elevation={0}
          sx={{
            p: 6,
            border: '1px solid',
            borderColor: 'divider',
            textAlign: 'center',
          }}
        >
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            Two versions needed
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Upload at least two versions of this project, run an
            Analysis on each, then compare them here.
          </Typography>
          <Button variant="contained" component={Link} to={`/projects/${id}`}>
            Go to project
          </Button>
        </Paper>
      </Box>
    )
  }

  const selectors = (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      <FormControl size="small" sx={{ minWidth: 200 }}>
        <InputLabel id="baseline-label">Baseline version</InputLabel>
        <Select
          labelId="baseline-label"
          label="Baseline version"
          value={effectiveBaselineId}
          onChange={(event) => setBaselineId(event.target.value)}
        >
          {versions.map((version) => (
            <MenuItem
              key={version.id}
              value={String(version.id)}
              disabled={String(version.id) === effectiveComparedId}
            >
              Version {version.version_number}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <FormControl size="small" sx={{ minWidth: 200 }}>
        <InputLabel id="compared-label">Compared version</InputLabel>
        <Select
          labelId="compared-label"
          label="Compared version"
          value={effectiveComparedId}
          onChange={(event) => setComparedId(event.target.value)}
        >
          {versions.map((version) => (
            <MenuItem
              key={version.id}
              value={String(version.id)}
              disabled={String(version.id) === effectiveBaselineId}
            >
              Version {version.version_number}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  )

  const sideEmptyState = (label, version) => (
    <Alert severity="info">
      {label} (Version {version.version_number}) has no completed
      Analysis yet. Run one from the{' '}
      <Button
        component={Link}
        to={`/projects/${id}`}
        size="small"
        sx={{ verticalAlign: 'baseline', p: 0, minWidth: 0 }}
      >
        project screen
      </Button>{' '}
      to compare it.
    </Alert>
  )

  const bothReady =
    baselineOutcome !== null && comparedOutcome !== null

  return (
    <Box>
      <Button component={Link} to={`/projects/${id}`} sx={{ mb: 2 }}>
        ← Back to project
      </Button>

      <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
        {project.name} — Compare versions
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        The newest completed Analysis of each version, side by side.
      </Typography>

      <Paper
        elevation={0}
        sx={{ p: 2.5, border: '1px solid', borderColor: 'divider', mb: 3 }}
      >
        {selectors}
      </Paper>

      {baselineAnalyses.isFetched && !baselineOutcome && baselineVersion && (
        <Box sx={{ mb: 2 }}>
          {sideEmptyState('Baseline', baselineVersion)}
        </Box>
      )}
      {comparedAnalyses.isFetched && !comparedOutcome && comparedVersion && (
        <Box sx={{ mb: 2 }}>
          {sideEmptyState('Compared', comparedVersion)}
        </Box>
      )}

      {bothReady && (
        <>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Metric delta
              </Typography>
              <CompareTable
                baseline={baselineOutcome}
                compared={comparedOutcome}
                catalogByName={catalogByName}
              />
            </Box>

            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Across versions
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: '1fr',
                    md: 'repeat(2, 1fr)',
                  },
                  gap: 2,
                }}
              >
                {HEADLINE_METRICS.map((name) => {
                  const baselineMetric = (
                    baselineOutcome.metrics ?? []
                  ).find((metric) => metric.name === name)
                  const comparedMetric = (
                    comparedOutcome.metrics ?? []
                  ).find((metric) => metric.name === name)
                  const catalogEntry = catalogByName.get(name)

                  return (
                    <Paper
                      key={name}
                      elevation={0}
                      sx={{
                        p: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Typography
                        variant="subtitle2"
                        sx={{ fontWeight: 700, mb: 1 }}
                      >
                        {catalogEntry?.display_name ?? name}
                      </Typography>
                      <MetricCompareChart
                        displayName={catalogEntry?.display_name ?? name}
                        unit={catalogEntry?.unit ?? ''}
                        baseline={{
                          label: `Version ${baselineVersion?.version_number}`,
                          value: comparisonScalar(baselineMetric),
                        }}
                        compared={{
                          label: `Version ${comparedVersion?.version_number}`,
                          value: comparisonScalar(comparedMetric),
                        }}
                      />
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          mt: 0.5,
                        }}
                      >
                        <Typography variant="caption" color="text.secondary">
                          {baselineVersion
                            ? `v${baselineVersion.version_number}: ${metricValueLabel(
                                baselineMetric,
                                comparisonScalar(baselineMetric),
                                catalogEntry?.unit ?? '',
                              )}`
                            : '—'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {comparedVersion
                            ? `v${comparedVersion.version_number}: ${metricValueLabel(
                                comparedMetric,
                                comparisonScalar(comparedMetric),
                                catalogEntry?.unit ?? '',
                              )}`
                            : '—'}
                        </Typography>
                      </Box>
                    </Paper>
                  )
                })}
              </Box>
            </Box>
          </Box>
        </>
      )}
    </Box>
  )
}
