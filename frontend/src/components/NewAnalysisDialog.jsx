import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Radio,
  RadioGroup,
  Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'

import { extractErrorMessage } from '../api/errors'
import { useCreateAnalysis, useMetrics } from '../api/queries'
import { ArrowDownwardIcon } from './icons'
import { ErrorModal } from './ErrorModal'
import { MetricPicker } from './MetricPicker'

/**
 * The Analysis creation dialog (frontend spec: "create an Analysis
 * for a version with metrics selected from the public catalog").
 * Pick one uploaded version, tick metrics from the catalog grouped
 * by category, and create — the backend returns immediately with a
 * PENDING Analysis that appears in the project's analysis history.
 * Creating with no metrics is blocked client-side with a clear
 * message (the backend enforces the same rule).
 *
 * The parent mounts this dialog only while it is open, so every
 * opening starts from fresh state (newest version preselected, no
 * metrics ticked, no error).
 */
export function NewAnalysisDialog({
  onClose,
  projectId,
  versions,
  onCreated,
}) {
  const metricsQuery = useMetrics()
  const create = useCreateAnalysis(projectId)

  const [versionId, setVersionId] = useState(() =>
    versions[0]?.id ? String(versions[0].id) : '',
  )
  const [selected, setSelected] = useState(() => new Set())
  const [aiRequested, setAiRequested] = useState(true)
  const [error, setError] = useState(null)

  const selectedNames = useMemo(
    () => (metricsQuery.data ?? []).filter((m) => selected.has(m.name)).map((m) => m.name),
    [metricsQuery.data, selected],
  )

  function handleClose() {
    setError(null)
    onClose()
  }

  function handleToggle(name) {
    setSelected((previous) => {
      const next = new Set(previous)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
    setError(null)
  }

  function handleToggleGroup(names, checked) {
    setSelected((previous) => {
      const next = new Set(previous)
      for (const name of names) {
        if (checked) next.add(name)
        else next.delete(name)
      }
      return next
    })
    setError(null)
  }

  async function handleCreate() {
    setError(null)

    if (!versionId) {
      setError('Choose a version to analyze.')
      return
    }

    if (selectedNames.length === 0) {
      setError('Select at least one metric to create the analysis.')
      return
    }

    try {
      const analysis = await create.mutateAsync({
        project_version: versionId,
        metrics: selectedNames,
        ai_requested: aiRequested,
      })
      onCreated(analysis)
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  const hasVersions = versions.length > 0

  return (
    <Dialog open onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>New analysis</DialogTitle>
      <DialogContent dividers>
        {!hasVersions ? (
          <Alert severity="info">
            Upload a version first — an analysis needs a .py file or a
            project ZIP to run against.
          </Alert>
        ) : (
          <>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              Project version
            </Typography>
            <RadioGroup
              row
              value={versionId}
              onChange={(event) => setVersionId(event.target.value)}
            >
              {versions.map((version) => (
                <FormControlLabel
                  key={version.id}
                  value={String(version.id)}
                  control={<Radio size="small" />}
                  label={`Version ${version.version_number}`}
                />
              ))}
            </RadioGroup>

            <Box sx={{ mt: 3 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  mb: 1,
                }}
              >
                <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                  Metrics
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {selectedNames.length} of {metricsQuery.data?.length ?? 0}{' '}
                  selected
                </Typography>
              </Box>

              {metricsQuery.isLoading ? (
                <Box sx={{ display: 'grid', placeItems: 'center', py: 6 }}>
                  <CircularProgress size={28} />
                </Box>
              ) : metricsQuery.isError ? (
                <Alert severity="error">
                  {extractErrorMessage(metricsQuery.error)}
                </Alert>
              ) : (
                <>
                  {/* The full catalog is longer than the visible area;
                      the hint + bounded scroll panel below make it clear
                      the list continues instead of looking finished. */}
                  {metricsQuery.data.length > 0 && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        mb: 1,
                      }}
                    >
                      <ArrowDownwardIcon sx={{ fontSize: '0.9rem' }} />
                      All {metricsQuery.data.length} metrics are listed
                      below in{' '}
                      {
                        new Set(
                          metricsQuery.data.map((metric) => metric.category),
                        ).size
                      }{' '}
                      groups — the list scrolls, so keep going to see the
                      rest.
                    </Typography>
                  )}
                  <Box
                    sx={{
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1.5,
                      px: 1.5,
                      py: 0.75,
                      maxHeight: 340,
                      overflowY: 'auto',
                    }}
                  >
                    <MetricPicker
                      metrics={metricsQuery.data}
                      selected={selected}
                      onToggle={handleToggle}
                      onToggleGroup={handleToggleGroup}
                    />
                  </Box>
                </>
              )}
            </Box>

            <Box sx={{ mt: 3 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={aiRequested}
                    onChange={(event) =>
                      setAiRequested(event.target.checked)
                    }
                    size="small"
                  />
                }
                label="AI explanations"
              />
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', ml: 3.5 }}
              >
                When the analysis completes, its computed results are
                sent to an LLM for an overall summary and per-metric
                explanations. Leave on for the full report; turn it off
                for a cheap, fast run.
              </Typography>
            </Box>
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose}>Cancel</Button>
        {hasVersions && (
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={create.isPending || metricsQuery.isLoading}
          >
            {create.isPending ? 'Creating…' : 'Create analysis'}
          </Button>
        )}
      </DialogActions>

      {/* Action errors (validation or the backend's reply) surface as
          a top-of-screen modal so they cannot be missed. */}
      <ErrorModal
        open={Boolean(error)}
        title="Could not create the analysis"
        message={error}
        onClose={() => setError(null)}
      />
    </Dialog>
  )
}
