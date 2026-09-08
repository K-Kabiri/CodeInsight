import { Chip } from '@mui/material'

import { CheckCircleIcon, ErrorIcon, ScheduleIcon } from './icons'

// The Analysis lifecycle colors, shared by every screen that shows a
// status (project history, Analyses list, detail header, metric cards).
// Kept module-local: react-refresh only allows component exports.
const STATUS_COLORS = {
  PENDING: 'warning',
  RUNNING: 'warning',
  COMPLETED: 'success',
  FAILED: 'error',
}

// Each status also gets a small glyph so colors never carry the
// meaning alone.
const STATUS_ICONS = {
  PENDING: ScheduleIcon,
  RUNNING: ScheduleIcon,
  COMPLETED: CheckCircleIcon,
  FAILED: ErrorIcon,
}

export function StatusChip({ status }) {
  const Icon = STATUS_ICONS[status] ?? null
  return (
    <Chip
      size="small"
      label={status}
      variant="outlined"
      color={STATUS_COLORS[status] ?? 'default'}
      icon={Icon ? <Icon sx={{ fontSize: '0.9rem !important' }} /> : undefined}
    />
  )
}
