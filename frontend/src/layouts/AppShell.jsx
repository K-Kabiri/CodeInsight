import {
  Box,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from '@mui/material'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/projects', label: 'Projects' },
  { to: '/analyses', label: 'Analyses' },
]

/**
 * The Command Center shell (prototype variant A): dark sidebar with
 * the brand, navigation, and a red "Log out" item pinned to the
 * bottom; the routed page renders into the main area.
 */
export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Box
        component="aside"
        sx={{
          width: 220,
          flexShrink: 0,
          bgcolor: '#0b0e15',
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          px: 1.5,
          py: 2,
        }}
      >
        <Typography
          variant="h6"
          sx={{ fontWeight: 800, px: 1, pb: 2 }}
        >
          Code
          <Box component="span" sx={{ color: 'primary.main' }}>
            Insight
          </Box>
        </Typography>

        <List sx={{ p: 0 }}>
          {NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.to === '/'}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: 'text.secondary',
                '&.active': {
                  bgcolor: 'rgba(108, 140, 255, 0.16)',
                  color: 'text.primary',
                  fontWeight: 700,
                },
                '&:hover': { color: 'text.primary' },
              }}
            >
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>

        <Box sx={{ flexGrow: 1 }} />
        <Divider sx={{ mb: 1 }} />

        {user && (
          <Typography
            variant="caption"
            sx={{ px: 1, pb: 1, color: 'text.secondary' }}
          >
            Signed in as{' '}
            <Box
              component="strong"
              sx={{ color: 'text.primary' }}
            >
              {user.username}
            </Box>
          </Typography>
        )}

        <ListItemButton
          onClick={handleLogout}
          sx={{
            borderRadius: 2,
            color: 'error.main',
            '&:hover': {
              color: 'error.main',
              bgcolor: 'rgba(255, 107, 107, 0.08)',
            },
          }}
        >
          <ListItemText primary="Log out" />
        </ListItemButton>
      </Box>

      <Box
        component="main"
        sx={{ flex: 1, minWidth: 0, p: 3 }}
      >
        <Outlet />
      </Box>
    </Box>
  )
}
