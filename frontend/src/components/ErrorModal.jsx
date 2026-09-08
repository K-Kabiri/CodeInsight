import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material'

import { ReportIcon } from './icons'

/**
 * A top-of-screen error modal (`role="alertdialog"`) for action
 * failures that are easy to miss as inline alerts — e.g. creating an
 * Analysis with no metrics selected. The modal appears near the top
 * of the page, over whatever form is open, and blocks until the user
 * acknowledges it with OK.
 */
export function ErrorModal({
  open,
  title = 'Something went wrong',
  message,
  onClose,
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      role="alertdialog"
      sx={{
        '& .MuiDialog-container': {
          alignItems: 'flex-start',
          pt: 8,
        },
      }}
    >
      <DialogTitle>
        <Box
          component="span"
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 1,
            color: 'error.main',
          }}
        >
          <ReportIcon />
          {title}
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        <Typography>{message}</Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button variant="contained" onClick={onClose} autoFocus>
          OK
        </Button>
      </DialogActions>
    </Dialog>
  )
}
