import { Box, Typography } from '@mui/material'

import { ProjectsTable } from '../components/ProjectsTable'

/**
 * The dedicated Projects screen (/projects, prototype variant P): a
 * full listing of the user's projects with version uploads reachable
 * from each row. The table card is shared with the dashboard.
 */
export default function ProjectsPage() {
  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
        Projects
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Every project you upload code to — open one to manage its
        versions and run analyses.
      </Typography>
      <ProjectsTable />
    </Box>
  )
}
