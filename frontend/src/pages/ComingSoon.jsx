import { Box, Paper, Typography } from '@mui/material'

/**
 * Placeholder for a screen that a later frontend slice builds.
 */
export default function ComingSoon({ title }) {
  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
        {title}
      </Typography>
      <Paper
        elevation={0}
        sx={{
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography color="text.secondary">
          This screen is part of a later slice of the frontend work.
        </Typography>
      </Paper>
    </Box>
  )
}
