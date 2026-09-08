import {
  Box,
  Chip,
  CircularProgress,
  Paper,
  Typography,
} from '@mui/material'

import { useMetrics } from '../api/queries'
import { withAlpha } from '../components/color'
import {
  categoryAccent,
  directionHint,
  groupMetricsByCategory,
} from '../components/metricCatalog'
import {
  AutoAwesomeIcon,
  MenuBookIcon,
  ScienceIcon,
} from '../components/icons'

function MetricCard({ metric, accent }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: withAlpha(accent, 0.32),
        backgroundImage: `linear-gradient(180deg, ${withAlpha(
          accent,
          0.08,
        )}, transparent 62%)`,
        boxShadow: `0 0 0 1px ${withAlpha(accent, 0.1)}, 0 12px 24px -18px ${withAlpha(accent, 0.55)}`,
        transition:
          'transform 200ms ease, box-shadow 200ms ease, border-color 200ms ease',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        height: '100%',
        '&:hover': {
          transform: 'translateY(-3px)',
          borderColor: withAlpha(accent, 0.75),
          boxShadow: `0 0 0 1px ${withAlpha(
            accent,
            0.45,
          )}, 0 0 22px ${withAlpha(accent, 0.3)}, 0 18px 32px -16px ${withAlpha(accent, 0.6)}`,
        },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <ScienceIcon
          sx={{ color: accent, fontSize: 20, filter: 'drop-shadow(0 0 6px ' + withAlpha(accent, 0.7) + ')' }}
        />
        <Typography
          component="span"
          sx={{ fontWeight: 700, fontSize: '0.95rem' }}
        >
          {metric.display_name}
        </Typography>
        <Typography
          component="span"
          variant="caption"
          sx={{
            color: 'text.secondary',
            fontFamily: 'monospace',
          }}
        >
          {metric.name}
        </Typography>
      </Box>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ fontSize: '0.82rem', lineHeight: 1.7, flex: 1 }}
      >
        {metric.description}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
          {metric.unit && (
            <Chip
              size="small"
              label={metric.unit}
              variant="outlined"
              sx={{ height: 18, fontSize: '0.65rem' }}
            />
          )}
          {metric.supports_llm && (
            <Chip
              size="small"
              icon={
                <AutoAwesomeIcon sx={{ fontSize: '0.75rem !important' }} />
              }
              label="AI-explained"
              variant="outlined"
              color="secondary"
              sx={{ height: 18, fontSize: '0.65rem' }}
            />
          )}
        </Box>
        {directionHint(metric) && (
          <Typography variant="caption" color="text.secondary">
            {directionHint(metric)}
          </Typography>
        )}
      </Box>
    </Paper>
  )
}

/**
 * The metric catalog screen (/metrics, prototype variant M): the
 * public catalog grouped by category, each metric with its display
 * name, canonical name, unit, description, and higher-is-better hint.
 */
export default function MetricCatalogPage() {
  const metrics = useMetrics()
  const groups = groupMetricsByCategory(metrics.data ?? [])
  const count = metrics.data?.length ?? 0

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
          mb: 0.5,
        }}
      >
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Metric catalog
        </Typography>
        {count > 0 && (
          <Chip
            label={`${count} metrics · each documented`}
            variant="outlined"
            size="small"
          />
        )}
      </Box>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        The full catalog behind every analysis — definitions,
        units, and whether higher values are better.
      </Typography>

      {metrics.isLoading ? (
        <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : groups.length === 0 ? (
        <Paper
          elevation={0}
          sx={{
            p: 6,
            border: '1px solid',
            borderColor: 'divider',
            textAlign: 'center',
          }}
        >
          <MenuBookIcon
            sx={{ color: 'primary.main', fontSize: 44, mb: 1 }}
          />
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
            Catalog unavailable
          </Typography>
          <Typography color="text.secondary">
            The metric catalog could not be loaded.
          </Typography>
        </Paper>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {groups.map((group) => {
            const accent = categoryAccent(group.category)
            return (
              <Box key={group.category}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1.25,
                    mb: 1.5,
                  }}
                >
                  <Box
                    aria-hidden
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      bgcolor: accent,
                      flexShrink: 0,
                      boxShadow: `0 0 10px ${withAlpha(accent, 0.9)}`,
                    }}
                  />
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 700 }}
                  >
                    {group.category}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: {
                      xs: '1fr',
                      md: 'repeat(2, 1fr)',
                      lg: 'repeat(3, 1fr)',
                    },
                    gap: 1.5,
                  }}
                >
                  {group.metrics.map((metric) => (
                    <MetricCard
                      key={metric.name}
                      metric={metric}
                      accent={accent}
                    />
                  ))}
                </Box>
              </Box>
            )
          })}
        </Box>
      )}
    </Box>
  )
}
