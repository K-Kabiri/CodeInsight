import {
  Avatar,
  Box,
  Button,
  Chip,
  Paper,
  Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'

import { useDashboardStats, useMetrics, useProjects } from '../api/queries'
import { useAuth } from '../auth/useAuth'
import { withAlpha } from '../components/color'
import {
  AutoAwesomeIcon,
  FolderCopyIcon,
  LogoutIcon,
  MailOutlineIcon,
  QueryStatsIcon,
  ScheduleIcon,
} from '../components/icons'
import { formatLongDate } from '../components/results/format'

// One accent per aggregate so the stat tiles read as a little color
// band across the profile screen.
const STAT_ACCENTS = ['#6c8cff', '#b07cff', '#5ee6c8']

function StatCard({ label, value, icon: Icon, accent = '#6c8cff' }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
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
      }}
    >
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: 2,
          display: 'grid',
          placeItems: 'center',
          bgcolor: withAlpha(accent, 0.12),
          boxShadow: `inset 0 0 0 1px ${withAlpha(accent, 0.25)}`,
        }}
      >
        <Icon sx={{ color: accent, fontSize: 21 }} />
      </Box>
      <Typography variant="h5" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Paper>
  )
}

/**
 * The user's profile screen (/profile): a read-only summary of the
 * signed-in account (username, membership date, email only when the
 * account actually has one — sign-up never collects it) plus the same
 * aggregates the dashboard shows. Data comes from /api/me/ and the
 * existing list endpoints.
 */
export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const metrics = useMetrics()
  const projects = useProjects(1)
  const stats = useDashboardStats()

  const initial = (user?.username ?? '?').charAt(0).toUpperCase()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>
        Profile
      </Typography>

      <Paper
        elevation={0}
        sx={{
          position: 'relative',
          overflow: 'hidden',
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
          mb: 3,
          backgroundImage:
            'radial-gradient(640px 260px at 90% -40%, rgba(108, 140, 255, 0.24), transparent 70%), radial-gradient(460px 240px at -5% 130%, rgba(94, 230, 200, 0.16), transparent 70%)',
          display: 'flex',
          alignItems: 'center',
          gap: 3,
          flexWrap: 'wrap',
        }}
      >
        {/* Decorative colour orb behind the account identity. */}
        <Box
          aria-hidden
          sx={{
            position: 'absolute',
            right: -60,
            top: -80,
            width: 220,
            height: 220,
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(108, 140, 255, 0.28), transparent 70%)',
            filter: 'blur(2px)',
            pointerEvents: 'none',
          }}
        />
        <Avatar
          sx={{
            width: 86,
            height: 86,
            fontSize: '2.1rem',
            fontWeight: 800,
            background: 'linear-gradient(135deg, #6c8cff, #5ee6c8)',
            boxShadow:
              '0 0 0 4px rgba(108, 140, 255, 0.25), 0 10px 28px -8px rgba(108, 140, 255, 0.7)',
          }}
        >
          {initial}
        </Avatar>
        <Box
          sx={{
            flex: 1,
            minWidth: 220,
            position: 'relative',
            zIndex: 1,
          }}
        >
          <Typography variant="h4" sx={{ fontWeight: 800 }}>
            {user?.username ?? '…'}
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 1.5 }}>
            @{user?.username ?? '…'}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {user?.email && (
              <Chip
                size="small"
                icon={
                  <MailOutlineIcon
                    sx={{ fontSize: '0.9rem !important' }}
                  />
                }
                label={user.email}
                variant="outlined"
              />
            )}
            <Chip
              size="small"
              icon={
                <ScheduleIcon sx={{ fontSize: '0.9rem !important' }} />
              }
              label={`Member since ${formatLongDate(user?.date_joined)}`}
              variant="outlined"
            />
          </Box>
        </Box>
        <Button
          variant="outlined"
          color="error"
          startIcon={<LogoutIcon />}
          onClick={handleLogout}
          sx={{ position: 'relative', zIndex: 1 }}
        >
          Log out
        </Button>
      </Paper>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(3, 1fr)',
          },
          gap: 2,
        }}
      >
        <StatCard
          label="Metrics available"
          value={metrics.data?.length ?? '…'}
          icon={AutoAwesomeIcon}
          accent={STAT_ACCENTS[0]}
        />
        <StatCard
          label="Projects"
          value={projects.data?.count ?? 0}
          icon={FolderCopyIcon}
          accent={STAT_ACCENTS[1]}
        />
        <StatCard
          label="Analyses"
          value={stats.data?.analysesCount ?? 0}
          icon={QueryStatsIcon}
          accent={STAT_ACCENTS[2]}
        />
      </Box>
    </Box>
  )
}
