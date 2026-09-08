import {
  Avatar,
  Box,
  Button,
  Chip,
  Paper,
  Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'

import {
  useDashboardStats,
  useProjects,
} from '../api/queries'
import { useAuth } from '../auth/useAuth'
import { withAlpha } from '../components/color'
import { ProjectsTable } from '../components/ProjectsTable'
import { StatusChip } from '../components/StatusChip'
import {
  FolderCopyIcon,
  PersonIcon,
  QueryStatsIcon,
  ReceiptLongIcon,
  ScheduleIcon,
  ScienceIcon,
} from '../components/icons'
import { formatDateTime, formatLongDate } from '../components/results/format'

// Soft neon lift shared by the dashboard's summary cards: a gentle
// translate + accent-tinted border and glow while hovering.
function hoverLift(accent = '#6c8cff') {
  return {
    transition:
      'transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease',
    '&:hover': {
      transform: 'translateY(-2px)',
      borderColor: withAlpha(accent, 0.55),
      boxShadow: `0 0 0 1px ${withAlpha(
        accent,
        0.25,
      )}, 0 16px 30px -16px ${withAlpha(accent, 0.6)}`,
    },
  }
}

function KpiCard({ label, value, footer, loading, icon: Icon, accent = '#6c8cff' }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        gap: 0.75,
        ...hoverLift(accent),
      }}
    >
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: 2,
          display: 'grid',
          placeItems: 'center',
          bgcolor: withAlpha(accent, 0.12),
          boxShadow: `inset 0 0 0 1px ${withAlpha(accent, 0.25)}`,
        }}
      >
        <Icon sx={{ color: accent, fontSize: 24 }} />
      </Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>
        {loading ? '…' : value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      {footer && (
        <Typography
          variant="caption"
          sx={{ color: 'success.main', mt: 0.25 }}
        >
          {footer}
        </Typography>
      )}
    </Paper>
  )
}

function ProfileCard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const initial = (user?.username ?? '?').charAt(0).toUpperCase()

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.25,
        ...hoverLift('#5ee6c8'),
      }}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
        Profile
      </Typography>
      <Box
        component="button"
        type="button"
        onClick={() => navigate('/profile')}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          bgcolor: 'transparent',
          border: 'none',
          cursor: 'pointer',
          p: 0,
          textAlign: 'left',
          color: 'inherit',
          font: 'inherit',
        }}
      >
        <Avatar
          sx={{
            width: 38,
            height: 38,
            background:
              'linear-gradient(135deg, #6c8cff, #5ee6c8)',
            boxShadow: '0 0 0 2px rgba(108, 140, 255, 0.3)',
            fontWeight: 700,
          }}
        >
          {initial}
        </Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700 }} noWrap>
            {user?.username ?? '…'}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
          >
            @{user?.username ?? '…'} · view profile
          </Typography>
        </Box>
      </Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
        }}
      >
        <ScheduleIcon sx={{ color: 'text.secondary', fontSize: 15 }} />
        <Typography variant="caption" color="text.secondary" noWrap>
          Member since {formatLongDate(user?.date_joined)}
        </Typography>
      </Box>
    </Paper>
  )
}

function ActivityCard({ activity, loading }) {
  const buckets = activity ?? []
  const max = Math.max(1, ...buckets.map((day) => day.count))

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        ...hoverLift('#6c8cff'),
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 1.25,
        }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Activity
        </Typography>
        <Chip
          size="small"
          label="Last 7 days"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.7rem' }}
        />
      </Box>
      {loading ? (
        <Box sx={{ flex: 1, display: 'grid', placeItems: 'center' }}>
          <Typography color="text.secondary">Loading…</Typography>
        </Box>
      ) : (
        <Box
          data-testid="activity-chart"
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'flex-end',
            gap: 1.25,
            height: 92,
          }}
        >
          {buckets.map((day) => (
            <Box
              key={day.label}
              sx={{
                flex: 1,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: 0.5,
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontSize: '0.65rem', lineHeight: 1 }}
              >
                {day.count}
              </Typography>
              <Box
                sx={{
                  width: '70%',
                  height: `${Math.max(4, (day.count / max) * 100)}%`,
                  borderRadius: '5px 5px 0 0',
                  background:
                    'linear-gradient(180deg, #6c8cff, rgba(108,140,255,.35))',
                  boxShadow: '0 0 10px rgba(108,140,255,0.35)',
                }}
              />
              <Typography variant="caption" color="text.secondary">
                {day.label}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Paper>
  )
}

function RecentAnalysesCard({ analyses, loading }) {
  const navigate = useNavigate()
  const recent = (analyses ?? []).slice(0, 5)

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        ...hoverLift('#b07cff'),
      }}
    >
      <Typography
        variant="subtitle1"
        sx={{ fontWeight: 700, mb: 1 }}
      >
        Recent analyses
      </Typography>
      {loading ? (
        <Typography color="text.secondary">Loading…</Typography>
      ) : recent.length === 0 ? (
        <Box sx={{ flex: 1 }}>
          <ScienceIcon
            sx={{ color: 'primary.main', fontSize: 28, mb: 0.75 }}
          />
          <Typography color="text.secondary" variant="body2">
            Run your first analysis to see it here.
          </Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          {recent.map((analysis) => {
            const failedMetrics = (analysis.metrics ?? []).filter(
              (metric) => metric.status === 'FAILED',
            ).length
            return (
              <Box
                key={analysis.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/analyses/${analysis.id}`)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    navigate(`/analyses/${analysis.id}`)
                  }
                }}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 1.5,
                  py: 0.65,
                  borderRadius: 1.5,
                  px: 1,
                  cursor: 'pointer',
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600 }}
                    noWrap
                  >
                    Analysis #{analysis.id}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                  >
                    {formatDateTime(analysis.created_at)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {failedMetrics > 0 && (
                    <Chip
                      size="small"
                      label={`${failedMetrics} failed`}
                      color="error"
                      variant="outlined"
                      sx={{ height: 18, fontSize: '0.65rem' }}
                    />
                  )}
                  <StatusChip status={analysis.status} />
                </Box>
              </Box>
            )
          })}
        </Box>
      )}
      {!loading && recent.length > 0 && (
        <Button
          size="small"
          endIcon={<ReceiptLongIcon sx={{ fontSize: 16 }} />}
          onClick={() => navigate('/analyses')}
          sx={{ alignSelf: 'flex-start', mt: 0.5 }}
        >
          View all analyses
        </Button>
      )}
    </Paper>
  )
}

/**
 * Home / dashboard (prototype variant A layout): a top bar with the
 * user chip, two KPI cards (projects / analyses), a three-column row
 * of profile, 7-day activity and recent analyses, and the full-width
 * projects table. Every number comes from the real API — no
 * fabricated deltas.
 */
export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const stats = useDashboardStats()
  const projects = useProjects(1)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 2,
          flexWrap: 'wrap',
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Dashboard
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.25 }}>
            Your code quality at a glance.
          </Typography>
        </Box>
        {user && (
          <Button
            variant="outlined"
            startIcon={<PersonIcon />}
            onClick={() => navigate('/profile')}
          >
            {user.username}
          </Button>
        )}
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            md: 'repeat(2, 1fr)',
          },
          gap: 2.5,
        }}
      >
        <KpiCard
          label="Total projects"
          value={projects.data?.count ?? 0}
          loading={projects.isLoading}
          icon={FolderCopyIcon}
          accent="#6c8cff"
        />
        <KpiCard
          label="Total analyses"
          value={stats.data?.analysesCount ?? 0}
          loading={stats.isLoading}
          icon={QueryStatsIcon}
          accent="#5ee6c8"
          footer={
            stats.data?.analysesThisWeek
              ? `${stats.data.analysesThisWeek} in the last 7 days`
              : null
          }
        />
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1.3fr 1fr' },
          gap: 2.5,
        }}
      >
        <ProfileCard />
        <ActivityCard
          activity={stats.data?.activity}
          loading={stats.isLoading}
        />
        <RecentAnalysesCard
          analyses={stats.data?.analyses}
          loading={stats.isLoading}
        />
      </Box>

      <ProjectsTable />
    </Box>
  )
}
