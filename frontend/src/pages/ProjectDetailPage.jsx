import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Typography,
} from '@mui/material'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { extractErrorMessage, isNotFound } from '../api/errors'
import {
  useDeleteAnalysis,
  useDeleteProject,
  useProject,
  useProjectAnalyses,
  useUploadVersion,
  useVersions,
} from '../api/queries'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { StatusChip } from '../components/StatusChip'
import { NewAnalysisDialog } from '../components/NewAnalysisDialog'
import {
  AddIcon,
  ArrowBackIcon,
  CompareArrowsIcon,
  DeleteIcon,
  UploadFileIcon,
} from '../components/icons'

function fileNameFromUrl(url) {
  return url.split('/').pop()
}

// A run that is still writing rows cannot be deleted until it settles.
function isInFlight(analysis) {
  return analysis.status === 'PENDING' || analysis.status === 'RUNNING'
}

/**
 * Project detail (prototype workbench's left panel): upload a .py or
 * .zip as the next version, browse the versions uploaded so far, and
 * create Analyses for a version with metrics picked from the catalog.
 */
export default function ProjectDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const projectQuery = useProject(id)
  const versionsQuery = useVersions(id)
  const analysesQuery = useProjectAnalyses(id)
  const upload = useUploadVersion(id)
  const deleteProject = useDeleteProject()
  const deleteAnalysis = useDeleteAnalysis()

  const inputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [analysisSuccess, setAnalysisSuccess] = useState(null)

  // Destructive confirmations (project / one analysis).
  const [projectDeleteOpen, setProjectDeleteOpen] = useState(false)
  const [analysisDeleteTarget, setAnalysisDeleteTarget] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  async function confirmProjectDelete() {
    setDeleteError(null)
    try {
      await deleteProject.mutateAsync(id)
      setProjectDeleteOpen(false)
      navigate('/', { replace: true })
    } catch (err) {
      setDeleteError(extractErrorMessage(err))
    }
  }

  function openAnalysisDelete(analysis) {
    setDeleteError(null)
    setAnalysisDeleteTarget(analysis)
  }

  function closeAnalysisDelete() {
    if (deleteAnalysis.isPending) return
    setAnalysisDeleteTarget(null)
    setDeleteError(null)
  }

  async function confirmAnalysisDelete() {
    if (!analysisDeleteTarget) return
    setDeleteError(null)
    try {
      await deleteAnalysis.mutateAsync(analysisDeleteTarget.id)
      setAnalysisDeleteTarget(null)
    } catch (err) {
      setDeleteError(extractErrorMessage(err))
    }
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0] ?? null
    setSelectedFile(file)
    setError(null)
    setSuccess(null)
  }

  async function handleUpload() {
    setError(null)
    setSuccess(null)

    if (!selectedFile) {
      setError('Choose a .py or .zip file to upload first.')
      return
    }

    try {
      const version = await upload.mutateAsync(selectedFile)
      setSuccess(
        `Uploaded ${selectedFile.name} as version ${version.version_number}.`,
      )
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  if (projectQuery.isLoading) {
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
  const versions = versionsQuery.data ?? []
  const analyses = analysesQuery.data ?? []

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
          flexWrap: 'wrap',
          mb: 3,
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Button
            component={Link}
            to="/"
            sx={{ mb: 1 }}
            startIcon={<ArrowBackIcon />}
          >
            Back to dashboard
          </Button>
          <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
            {project.name}
          </Typography>
          <Typography color="text.secondary">
            {project.description || 'No description.'}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={() => {
            setDeleteError(null)
            setProjectDeleteOpen(true)
          }}
        >
          Delete project
        </Button>
      </Box>

      <Paper
        elevation={0}
        sx={{
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
          mb: 3,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
          Upload a version
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Upload one .py file or a .zip archive of a Python project.
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            ref={inputRef}
            type="file"
            accept=".py,.zip"
            aria-label="Upload source file"
            onChange={handleFileChange}
            style={{
              position: 'absolute',
              width: 1,
              height: 1,
              opacity: 0,
              overflow: 'hidden',
            }}
          />
          <Button
            variant="outlined"
            onClick={() => inputRef.current?.click()}
          >
            {selectedFile ? selectedFile.name : 'Choose file…'}
          </Button>
          <Button
            variant="contained"
            startIcon={<UploadFileIcon />}
            onClick={handleUpload}
            disabled={upload.isPending}
          >
            {upload.isPending ? 'Uploading…' : 'Upload version'}
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" sx={{ mt: 2 }}>
            {success}
          </Alert>
        )}
      </Paper>

      <Paper
        elevation={0}
        sx={{ border: '1px solid', borderColor: 'divider' }}
      >
        <Box
          sx={{
            p: 2.5,
            pb: 1,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Versions
          </Typography>
          <Button
            variant="outlined"
            startIcon={<CompareArrowsIcon />}
            component={Link}
            to={`/projects/${id}/compare`}
          >
            Compare versions
          </Button>
        </Box>
        <Divider />
        {versionsQuery.isLoading ? (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : versions.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No versions yet — upload your first .py or ZIP above.
            </Typography>
          </Box>
        ) : (
          // Scroll inside the box instead of stretching the page as
          // versions accumulate.
          <List sx={{ px: 2, maxHeight: 360, overflowY: 'auto' }}>
            {versions.map((version) => (
              <ListItem
                key={version.id}
                divider
                sx={{ px: 1 }}
              >
                <ListItemText
                  primary={`Version ${version.version_number}`}
                  secondary={fileNameFromUrl(version.source_file)}
                />
                <Typography
                  variant="caption"
                  color="text.secondary"
                >
                  {new Date(version.uploaded_at).toLocaleDateString()}
                </Typography>
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      <Paper
        elevation={0}
        sx={{ border: '1px solid', borderColor: 'divider', mt: 3 }}
      >
        <Box
          sx={{
            p: 2.5,
            pb: 1,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Analyses
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {
              setAnalysisSuccess(null)
              setDialogOpen(true)
            }}
          >
            New analysis
          </Button>
        </Box>
        <Divider />
        {analysisSuccess && (
          <Alert severity="success" sx={{ m: 2.5, mb: 0 }}>
            {analysisSuccess}
          </Alert>
        )}
        {analysesQuery.isLoading ? (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 6 }}>
            <CircularProgress size={28} />
          </Box>
        ) : analyses.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No analyses yet — pick a version and a set of metrics to
              run one.
            </Typography>
          </Box>
        ) : (
          // Same cap as the versions list: the history scrolls inside
          // its own paper rather than pushing the page forever.
          <List sx={{ px: 2, maxHeight: 360, overflowY: 'auto' }}>
            {analyses.map((analysis) => {
              const version = versions.find(
                (candidate) =>
                  String(candidate.id) === String(analysis.project_version),
              )
              return (
                <ListItemButton
                  key={analysis.id}
                  divider
                  sx={{ px: 1, borderRadius: 1 }}
                  onClick={() => navigate(`/analyses/${analysis.id}`)}
                >
                  <ListItemText
                    primary={`Analysis #${analysis.id}`}
                    secondary={
                      version
                        ? `Version ${version.version_number}`
                        : 'Version removed'
                    }
                  />
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                    >
                      {new Date(analysis.created_at).toLocaleDateString()}
                    </Typography>
                    <StatusChip status={analysis.status} />
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
                        openAnalysisDelete(analysis)
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </ListItemButton>
              )
            })}
          </List>
        )}
      </Paper>

      {dialogOpen && (
        <NewAnalysisDialog
          onClose={() => setDialogOpen(false)}
          projectId={id}
          versions={versions}
          onCreated={(analysis) => {
            setAnalysisSuccess(
              `Analysis #${analysis.id} created — status ${analysis.status}.`,
            )
            setDialogOpen(false)
          }}
        />
      )}

      <ConfirmDialog
        open={projectDeleteOpen}
        title="Delete project?"
        message={`"${project.name}" and all of its versions and analyses will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete project"
        busy={deleteProject.isPending}
        error={deleteError}
        onConfirm={confirmProjectDelete}
        onClose={() => {
          if (deleteProject.isPending) return
          setProjectDeleteOpen(false)
          setDeleteError(null)
        }}
      />
      <ConfirmDialog
        open={Boolean(analysisDeleteTarget)}
        title="Delete analysis?"
        message={`Analysis #${analysisDeleteTarget?.id ?? ''} and its metric results will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete analysis"
        busy={deleteAnalysis.isPending}
        error={deleteError}
        onConfirm={confirmAnalysisDelete}
        onClose={closeAnalysisDelete}
      />
    </Box>
  )
}
