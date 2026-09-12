import { Chip } from '@mui/material'

import {
  CheckCircleIcon,
  ErrorIcon,
  InfoOutlinedIcon,
  ScheduleIcon,
  WarningAmberIcon,
} from './icons'

// The Analysis lifecycle colors, shared by every screen that shows a
// status (project history, Analyses list, detail header, metric cards).
// Kept module-local: react-refresh only allows component exports.
const STATUS_COLORS = {
  PENDING: 'warning',
  RUNNING: 'warning',
  COMPLETED: 'success',
  FAILED: 'error',
  // Applicability states of a metric whose run finished without a
  // numeric claim (ADR-0001). They are deliberately not `success`:
  // a green "COMPLETED" beside a missing number is exactly the
  // confusion this status exists to remove (see MetricCard).
  NOT_APPLICABLE: 'info',
  PARTIAL: 'warning',
  NO_VALUE: 'default',
}

// Each status also gets a small glyph so colors never carry the
// meaning alone.
const STATUS_ICONS = {
  PENDING: ScheduleIcon,
  RUNNING: ScheduleIcon,
  COMPLETED: CheckCircleIcon,
  FAILED: ErrorIcon,
  NOT_APPLICABLE: InfoOutlinedIcon,
  PARTIAL: WarningAmberIcon,
  NO_VALUE: InfoOutlinedIcon,
}

// Statuses whose label differs from the wire value: an applicability
// state is a sentence for the user, not an enum.
const STATUS_LABELS = {
  NOT_APPLICABLE: 'Not applicable',
  PARTIAL: 'Partial',
  NO_VALUE: 'No value',
}

export function StatusChip({ status }) {
  const Icon = STATUS_ICONS[status] ?? null
  return (
    <Chip
      size="small"
      label={STATUS_LABELS[status] ?? status}
      variant="outlined"
      color={STATUS_COLORS[status] ?? 'default'}
      icon={Icon ? <Icon sx={{ fontSize: '0.9rem !important' }} /> : undefined}
    />
  )
}
