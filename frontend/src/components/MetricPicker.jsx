import {
  Box,
  Checkbox,
  Chip,
  FormControlLabel,
  Typography,
} from '@mui/material'

import {
  directionHint,
  groupMetricsByCategory,
} from './metricCatalog'

/**
 * The metric-selection checklist: the public catalog grouped by
 * category, each entry showing its display name, unit, description,
 * and a higher-is-better hint. The parent owns the selection state
 * (a Set of canonical names) so the dialog can count and validate.
 */
export function MetricPicker({ metrics, selected, onToggle, onToggleGroup }) {
  const groups = groupMetricsByCategory(metrics)

  return (
    <Box>
      {groups.map((group) => {
        const names = group.metrics.map((metric) => metric.name)
        const allSelected = names.every((name) => selected.has(name))
        const someSelected = names.some((name) => selected.has(name))

        return (
          <Box key={group.category} sx={{ mb: 2.5 }}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 0.5,
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                {group.category}
              </Typography>
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={allSelected}
                    indeterminate={someSelected && !allSelected}
                    onChange={(event) =>
                      onToggleGroup(names, event.target.checked)
                    }
                    slotProps={{
                      input: {
                        'aria-label': `Select all ${group.category}`,
                      },
                    }}
                  />
                }
                label="Select all"
                sx={{ m: 0, '& .MuiFormControlLabel-label': { fontSize: '0.8rem' } }}
              />
            </Box>

            {group.metrics.map((metric) => (
              <Box
                key={metric.name}
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 1,
                  py: 0.75,
                  px: 1,
                  borderRadius: 1.5,
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Checkbox
                  size="small"
                  checked={selected.has(metric.name)}
                  onChange={() => onToggle(metric.name)}
                  slotProps={{
                    input: {
                      'aria-label': `Select ${metric.display_name}`,
                    },
                  }}
                  sx={{ mt: -0.5 }}
                />
                <Box sx={{ minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography
                      component="span"
                      variant="body2"
                      sx={{ fontWeight: 600 }}
                    >
                      {metric.display_name}
                    </Typography>
                    <Typography
                      component="span"
                      variant="caption"
                      sx={{ color: 'text.secondary', fontFamily: 'monospace' }}
                    >
                      {metric.name}
                    </Typography>
                    {metric.unit && (
                      <Chip
                        size="small"
                        label={metric.unit}
                        variant="outlined"
                        sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                    )}
                    {directionHint(metric) && (
                      <Typography
                        component="span"
                        variant="caption"
                        sx={{ color: 'text.secondary' }}
                      >
                        {directionHint(metric)}
                      </Typography>
                    )}
                  </Box>
                  <Typography
                    variant="body2"
                    sx={{ color: 'text.secondary', fontSize: '0.8rem' }}
                  >
                    {metric.description}
                  </Typography>
                </Box>
              </Box>
            ))}
          </Box>
        )
      })}
    </Box>
  )
}
