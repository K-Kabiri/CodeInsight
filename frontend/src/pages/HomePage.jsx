import { Box, Paper, Typography } from '@mui/material'

import { useAuth } from '../auth/useAuth'

/**
 * Dashboard placeholder — the real Command Center (KPIs, projects
 * table, quick actions) arrives in the next frontend slice.
 */
export default function HomePage() {
  const { user } = useAuth()

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        Welcome back{user ? `, ${user.username}` : ''}.
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Your CodeInsight dashboard is on its way.
      </Typography>
      <Paper
        elevation={0}
        sx={{
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Projects, analyses, and version comparison arrive in the
          next slices of the frontend work.
        </Typography>
      </Paper>
    </Box>
  )
}
