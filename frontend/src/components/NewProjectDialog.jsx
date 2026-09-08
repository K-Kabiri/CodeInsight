import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from '@mui/material'
import { useCallback, useContext, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { extractErrorMessage } from '../api/errors'
import { useCreateProject } from '../api/queries'
import { NewProjectContext } from './NewProjectContext'

export function NewProjectProvider({ children }) {
  const [open, setOpen] = useState(false)
  const openDialog = useCallback(() => setOpen(true), [])
  const closeDialog = useCallback(() => setOpen(false), [])
  const value = useMemo(
    () => ({ open, openDialog, closeDialog }),
    [open, openDialog, closeDialog],
  )

  return (
    <NewProjectContext.Provider value={value}>
      {children}
    </NewProjectContext.Provider>
  )
}

/**
 * One "New project" dialog for the whole app, rendered by the shell
 * and driven by NewProjectProvider, so the sidebar quick action works
 * from any page. On success the projects list is invalidated, the
 * dialog closes, and the shell navigates straight into the created
 * project's screen (where the first version is uploaded); backend
 * field errors render inline.
 */
export function NewProjectDialog() {
  const { open, closeDialog } = useContext(NewProjectContext)
  const createProject = useCreateProject()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState(null)

  function reset() {
    setName('')
    setDescription('')
    setError(null)
  }

  function handleClose() {
    reset()
    closeDialog()
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    try {
      const project = await createProject.mutateAsync({ name, description })
      handleClose()
      if (project?.id) {
        navigate(`/projects/${project.id}`)
      }
    } catch (err) {
      setError(extractErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>New project</DialogTitle>
      <Box component="form" onSubmit={handleSubmit} noValidate>
        <DialogContent>
          <TextField
            label="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            fullWidth
            margin="normal"
            required
            autoFocus
          />
          <TextField
            label="Description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            fullWidth
            margin="normal"
            multiline
            minRows={2}
          />
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose}>Cancel</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={createProject.isPending}
          >
            {createProject.isPending ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  )
}
