import {
  Box,
  Divider,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material'
import { useContext } from 'react'
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import {
  NewProjectContext,
} from '../components/NewProjectContext'
import { NewProjectDialog } from '../components/NewProjectDialog'
import {
  AddIcon,
  FolderOpenIcon,
  LogoutIcon,
  MenuBookIcon,
  PersonIcon,
  ReceiptLongIcon,
  SpaceDashboardIcon,
} from '../components/icons'
import { pageBackgroundImage } from '../theme'

// Sidebar navigation, mirroring the prototype's Command Center list
// (dashboard / projects / analyses / metric catalog), each item with
// its Material glyph.
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: SpaceDashboardIcon, end: true },
  { to: '/projects', label: 'Projects', icon: FolderOpenIcon },
  { to: '/analyses', label: 'Analyses', icon: ReceiptLongIcon },
  { to: '/metrics', label: 'Metric catalog', icon: MenuBookIcon },
  { to: '/profile', label: 'Profile', icon: PersonIcon },
]

/**
 * The Command Center shell (prototype variant A): dark sidebar with
 * the brand, navigation (with icons), and a red "Log out" item pinned
 * to the bottom; the routed page renders into the main area.
 */
export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { openDialog } = useContext(NewProjectContext)

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
        backgroundImage: pageBackgroundImage,
      }}
    >
      <Box
        component="aside"
        sx={{
          width: 230,
          flexShrink: 0,
          bgcolor: '#0b0e15',
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          px: 1.5,
          py: 2,
          // The sidebar always fills the viewport and sticks to the
          // top while the page scrolls, so the bottom actions ("New
          // project", "Log out") stay visible at a fixed size.
          position: 'sticky',
          top: 0,
          height: '100vh',
          overflowY: 'auto',
        }}
      >
        <Typography
          variant="h6"
          sx={{ fontWeight: 800, px: 1, pb: 2 }}
        >
          Code
          <Box
            component="span"
            sx={{
              display: 'inline-block',
              backgroundImage:
                'linear-gradient(90deg, #6c8cff, #5ee6c8)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Insight
          </Box>
        </Typography>

        <List sx={{ p: 0 }}>
          {NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.end}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: 'text.secondary',
                '&.active': {
                  bgcolor: 'rgba(108, 140, 255, 0.16)',
                  color: 'text.primary',
                  fontWeight: 700,
                  boxShadow:
                    'inset 0 0 0 1px rgba(108, 140, 255, 0.3), 0 0 14px rgba(108, 140, 255, 0.18)',
                },
                '&:hover': { color: 'text.primary' },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 32,
                  color: 'inherit',
                  '& .MuiSvgIcon-root': { fontSize: 21 },
                }}
              >
                <item.icon />
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                sx={{
                  '& .MuiListItemText-primary': { fontSize: '0.9rem' },
                }}
              />
            </ListItemButton>
          ))}
        </List>

        <Box sx={{ flexGrow: 1 }} />
        <Divider sx={{ mb: 1, flexShrink: 0 }} />

        {user && (
          <Typography
            variant="caption"
            sx={{ px: 1, pb: 1, color: 'text.secondary', flexShrink: 0 }}
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
          onClick={openDialog}
          sx={{
            borderRadius: 2,
            mb: 0.5,
            // MUI's ListItemButton defaults to flexGrow: 1, which would
            // stretch these direct flex children to fill the sidebar —
            // pin them to content size like the nav items above.
            flexGrow: 0,
            flexShrink: 0,
            color: 'primary.main',
            '&:hover': {
              color: 'primary.main',
              bgcolor: 'rgba(108, 140, 255, 0.08)',
            },
          }}
        >
          <ListItemIcon
            sx={{
              minWidth: 32,
              color: 'inherit',
              '& .MuiSvgIcon-root': { fontSize: 21 },
            }}
          >
            <AddIcon />
          </ListItemIcon>
          <ListItemText
            primary="New project"
            sx={{
              '& .MuiListItemText-primary': { fontSize: '0.9rem' },
            }}
          />
        </ListItemButton>

        <ListItemButton
          onClick={handleLogout}
          sx={{
            borderRadius: 2,
            flexGrow: 0,
            flexShrink: 0,
            color: 'error.main',
            '&:hover': {
              color: 'error.main',
              bgcolor: 'rgba(255, 107, 107, 0.08)',
            },
          }}
        >
          <ListItemIcon
            sx={{
              minWidth: 32,
              color: 'inherit',
              '& .MuiSvgIcon-root': { fontSize: 21 },
            }}
          >
            <LogoutIcon />
          </ListItemIcon>
          <ListItemText
            primary="Log out"
            sx={{
              '& .MuiListItemText-primary': { fontSize: '0.9rem' },
            }}
          />
        </ListItemButton>
      </Box>

      <Box
        component="main"
        sx={{
          flex: 1,
          minWidth: 0,
          p: 3,
          position: 'relative',
        }}
      >
        {/* Keyed on the path so every navigation replays the entrance
            animation for the newly routed page. */}
        <Box key={location.pathname} className="dsh-page-enter">
          <Outlet />
        </Box>
      </Box>

      <NewProjectDialog />
    </Box>
  )
}
