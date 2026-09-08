import {
  Box,
  Button,
  CircularProgress,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { extractErrorMessage } from '../api/errors'
import {
  pageFromUrl,
  useAnalyses,
  useDeleteAnalysis,
} from '../api/queries'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { BarChartIcon, DeleteIcon, ReceiptLongIcon } from '../components/icons'
import { StatusChip } from '../components/StatusChip'
import { formatDateTime } from '../components/results/format'

// A run that is still writing rows cannot be deleted until it settles.
function isInFlight(analysis) {
  return analysis.status === 'PENDING' || analysis.status === 'RUNNING'
}

/**
 * The Analyses list (ticket 05, user story 12): every Analysis the
 * user has run, newest first, with status chips and timestamps. Rows
 * open the detail screen (/analyses/:id) which polls while the run
 * is in flight, and settled runs can be deleted from the row action.
 * Paginated one page at a time like the dashboard.
 */
export default function AnalysesPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  const analyses = useAnalyses(page)
  const deleteAnalysis = useDeleteAnalysis()
  const rows = analyses.data?.results ?? []

  function openDelete(analysis) {
    setDeleteError(null)
    setDeleteTarget(analysis)
  }

  function closeDelete() {
    if (deleteAnalysis.isPending) return
    setDeleteTarget(null)
    setDeleteError(null)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleteError(null)
    try {
      await deleteAnalysis.mutateAsync(deleteTarget.id)
      setDeleteTarget(null)
    } catch (error) {
      setDeleteError(extractErrorMessage(error))
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
        Analyses
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Every analysis run across your projects — open one to see its
        results as they complete.
      </Typography>

      {analyses.isLoading ? (
        <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : rows.length === 0 ? (
        <Paper
          elevation={0}
          sx={{
            p: 6,
            border: '1px solid',
            borderColor: 'divider',
            textAlign: 'center',
          }}
        >
          <BarChartIcon
            sx={{ color: 'primary.main', fontSize: 44, mb: 1 }}
          />
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            No analyses yet
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            Open a project, pick a version and a set of metrics, and
            your first analysis will show up here.
          </Typography>
          <Button variant="contained" onClick={() => navigate('/')}>
            Go to your projects
          </Button>
        </Paper>
      ) : (
        <Paper
          elevation={0}
          sx={{ border: '1px solid', borderColor: 'divider' }}
        >
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Analysis</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell>Finished</TableCell>
                  <TableCell align="right" />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((analysis) => (
                  <TableRow
                    key={analysis.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/analyses/${analysis.id}`)}
                  >
                    <TableCell sx={{ fontWeight: 600 }}>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                        }}
                      >
                        <ReceiptLongIcon
                          sx={{
                            color: 'text.secondary',
                            fontSize: 18,
                          }}
                        />
                        <span>Analysis #{analysis.id}</span>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={analysis.status} />
                    </TableCell>
                    <TableCell>
                      {formatDateTime(analysis.created_at)}
                    </TableCell>
                    <TableCell>
                      {formatDateTime(analysis.started_at)}
                    </TableCell>
                    <TableCell>
                      {formatDateTime(analysis.finished_at)}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        aria-label={`Delete analysis #${analysis.id}`}
                        size="small"
                        color="error"
                        disabled={isInFlight(analysis)}
                        title={
                          isInFlight(analysis)
                            ? 'Wait for the analysis to finish before deleting it'
                            : `Delete analysis #${analysis.id}`
                        }
                        onClick={(event) => {
                          event.stopPropagation()
                          openDelete(analysis)
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {(analyses.data?.next || page > 1) && (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 1,
                p: 2,
              }}
            >
              <Button
                disabled={page <= 1 || analyses.isFetching}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <Button
                disabled={!analyses.data?.next || analyses.isFetching}
                onClick={() =>
                  setPage(pageFromUrl(analyses.data?.next) ?? page + 1)
                }
              >
                Next
              </Button>
            </Box>
          )}
        </Paper>
      )}

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete analysis?"
        message={`Analysis #${deleteTarget?.id ?? ''} and its metric results will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete analysis"
        busy={deleteAnalysis.isPending}
        error={deleteError}
        onConfirm={confirmDelete}
        onClose={closeDelete}
      />
    </Box>
  )
}
