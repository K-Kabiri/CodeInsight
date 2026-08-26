import { Box, CircularProgress } from '@mui/material'
import { Navigate } from 'react-router-dom'

import { useAuth } from './useAuth'

/**
 * Guard for protected routes: while the stored session is being
 * confirmed against the API show a spinner; unauthenticated visitors
 * are sent to the login page.
 */
export function RequireAuth({ children }) {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <Box
        sx={{
          display: 'grid',
          placeItems: 'center',
          minHeight: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    )
  }

  if (status === 'anonymous') {
    return <Navigate to="/login" replace />
  }

  return children
}
