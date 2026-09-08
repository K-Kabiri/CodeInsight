import {
  Box,
  Button,
  Chip,
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
import { useContext, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { extractErrorMessage } from '../api/errors'
import { pageFromUrl, useDeleteProject, useProjects } from '../api/queries'
import { ConfirmDialog } from './ConfirmDialog'
import {
  NewProjectContext,
} from './NewProjectContext'
import { AddIcon, DeleteIcon, FolderOpenIcon, ScienceIcon } from './icons'

/**
 * The paginated projects table card (prototype dashboard variant A):
 * header with the project count and a "New project" action, then the
 * rows, and a guided empty state for first-time users. Shared by the
 * dashboard and the dedicated Projects page (/projects).
 */
export function ProjectsTable() {
  const navigate = useNavigate()
  const { openDialog } = useContext(NewProjectContext)
  const [page, setPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  const projects = useProjects(page)
  const deleteProject = useDeleteProject()
  const projectList = projects.data?.results ?? []
  const totalProjects = projects.data?.count ?? 0

  function openDelete(project) {
    setDeleteError(null)
    setDeleteTarget(project)
  }

  function closeDelete() {
    if (deleteProject.isPending) return
    setDeleteTarget(null)
    setDeleteError(null)
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleteError(null)
    try {
      await deleteProject.mutateAsync(deleteTarget.id)
      setDeleteTarget(null)
    } catch (error) {
      setDeleteError(extractErrorMessage(error))
    }
  }

  return (
    <>
      <Paper
        elevation={0}
        sx={{ border: '1px solid', borderColor: 'divider' }}
      >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
          px: 2.5,
          py: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FolderOpenIcon sx={{ color: 'primary.main', fontSize: 22 }} />
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Projects
          </Typography>
          {!projects.isLoading && (
            <Chip
              size="small"
              label={`${totalProjects}`}
              variant="outlined"
              sx={{ height: 20, fontSize: '0.7rem' }}
            />
          )}
        </Box>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={openDialog}
        >
          New project
        </Button>
      </Box>

      {projects.isLoading ? (
        <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : projectList.length === 0 ? (
        <Box sx={{ p: 5, textAlign: 'center' }}>
          <ScienceIcon
            sx={{ color: 'primary.main', fontSize: 44, mb: 1 }}
          />
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
            No projects yet
          </Typography>
          <Typography
            color="text.secondary"
            sx={{ mb: 3, maxWidth: 520, mx: 'auto' }}
          >
            Create a project, upload a Python file or a project ZIP, and
            run a full 12-metric analysis with evidence for every number.
          </Typography>
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 1.5,
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: 2,
              px: 2.5,
              py: 1.25,
              mb: 3,
              color: 'text.secondary',
              fontSize: '0.875rem',
            }}
          >
            <span>1. Name your project</span>
            <span aria-hidden>→</span>
            <span>2. Upload (.py / .zip)</span>
            <span aria-hidden>→</span>
            <span>3. Pick metrics &amp; analyze</span>
          </Box>
          <Box>
            <Button variant="contained" onClick={openDialog}>
              Create your first project
            </Button>
          </Box>
        </Box>
      ) : (
        <>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Description</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {projectList.map((project) => (
                  <TableRow
                    key={project.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/projects/${project.id}`)}
                  >
                    <TableCell sx={{ fontWeight: 600 }}>
                      {project.name}
                    </TableCell>
                    <TableCell>
                      {new Date(
                        project.created_at,
                      ).toLocaleDateString()}
                    </TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>
                      {project.description || '—'}
                    </TableCell>
                    <TableCell align="right">
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          gap: 0.5,
                        }}
                      >
                        <Button
                          size="small"
                          onClick={() =>
                            navigate(`/projects/${project.id}`)
                          }
                        >
                          Open
                        </Button>
                        <IconButton
                          aria-label={`Delete project ${project.name}`}
                          size="small"
                          color="error"
                          title={`Delete ${project.name}`}
                          onClick={(event) => {
                            event.stopPropagation()
                            openDelete(project)
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {(projects.data?.next || page > 1) && (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 1,
                p: 2,
              }}
            >
              <Button
                disabled={page <= 1 || projects.isFetching}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <Button
                disabled={!projects.data?.next || projects.isFetching}
                onClick={() =>
                  setPage(pageFromUrl(projects.data?.next) ?? page + 1)
                }
              >
                Next
              </Button>
            </Box>
          )}
        </>
      )}
    </Paper>
    <ConfirmDialog
      open={Boolean(deleteTarget)}
      title="Delete project?"
      message={`"${deleteTarget?.name ?? ''}" and all of its versions and analyses will be permanently removed. This cannot be undone.`}
      confirmLabel="Delete project"
      busy={deleteProject.isPending}
      error={deleteError}
      onConfirm={confirmDelete}
      onClose={closeDelete}
    />
    </>
  )
}
