import {
  Alert,
  Box,
  Button,
  Paper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

const FEATURES = [
  '12 metrics · each with a documented definition',
  'Every finding points at the exact function, class, and line',
  'Compare versions and watch quality change',
]

// The backend surfaces errors as DRF field errors; pick the first
// readable message for the form alert.
function extractErrorMessage(error) {
  const data = error?.response?.data
  if (!data) return 'Something went wrong. Please try again.'
  const first = (value) => (Array.isArray(value) ? value[0] : value)
  return (
    first(data.non_field_errors) ||
    first(data.username) ||
    first(data.password) ||
    first(data.detail) ||
    'Request failed. Please try again.'
  )
}

/**
 * Landing / Auth page (prototype variant L): brand hero beside a
 * login/sign-up card with tabs. Sign-up collects username + password
 * (the register endpoint's contract) plus a frontend-only password
 * confirmation.
 */
export default function LoginPage() {
  const { status, login, register } = useAuth()
  const navigate = useNavigate()

  const [tab, setTab] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  // Once authenticated (fresh login or already-signed-in visitor),
  // leave the landing page for the protected area.
  useEffect(() => {
    if (status === 'authenticated') {
      navigate('/', { replace: true })
    }
  }, [status, navigate])

  function switchTab(nextTab) {
    setTab(nextTab)
    setFormError(null)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError(null)

    if (tab === 'signup' && password !== confirmPassword) {
      setFormError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      if (tab === 'login') {
        await login(username, password)
      } else {
        await register(username, password)
      }
    } catch (error) {
      setFormError(extractErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1.1fr 1fr' },
        alignItems: 'center',
        gap: 6,
        px: { xs: 3, md: '8vw' },
        py: 4,
      }}
    >
      {/* Brand hero */}
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 2 }}>
          Code
          <Box component="span" sx={{ color: 'primary.main' }}>
            Insight
          </Box>
        </Typography>
        <Typography
          variant="h3"
          component="h1"
          sx={{
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            mb: 2,
          }}
        >
          Know exactly how your Python code quality evolves.
        </Typography>
        <Typography
          color="text.secondary"
          sx={{ maxWidth: 460, lineHeight: 1.6, mb: 3 }}
        >
          Upload a file or a project, pick your metrics, and get
          defensible, explainable analysis — complexity, coupling,
          smells, violations, duplication — with the evidence for
          every number.
        </Typography>
        <Box
          component="ul"
          sx={{
            listStyle: 'none',
            p: 0,
            m: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.25,
          }}
        >
          {FEATURES.map((feature) => (
            <Box
              component="li"
              key={feature}
              sx={{
                display: 'flex',
                gap: 1.5,
                alignItems: 'center',
                color: 'text.secondary',
                fontSize: '0.9rem',
              }}
            >
              <Box
                component="span"
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: 'primary.main',
                  flexShrink: 0,
                }}
              />
              {feature}
            </Box>
          ))}
        </Box>
      </Box>

      {/* Auth card */}
      <Paper
        elevation={0}
        sx={{
          p: 3,
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 4,
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.35)',
        }}
      >
        <Tabs
          value={tab}
          onChange={(_, nextTab) => switchTab(nextTab)}
          variant="fullWidth"
          sx={{ mb: 2 }}
        >
          <Tab value="login" label="Log in" />
          <Tab value="signup" label="Sign up" />
        </Tabs>

        <Box component="form" onSubmit={handleSubmit} noValidate>
          <TextField
            label="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            fullWidth
            margin="normal"
            autoComplete="username"
            required
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            fullWidth
            margin="normal"
            autoComplete={
              tab === 'login' ? 'current-password' : 'new-password'
            }
            required
          />
          {tab === 'signup' && (
            <TextField
              label="Confirm password"
              type="password"
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(event.target.value)
              }
              fullWidth
              margin="normal"
              autoComplete="new-password"
              required
            />
          )}

          {formError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {formError}
            </Alert>
          )}

          <Button
            type="submit"
            variant="contained"
            fullWidth
            size="large"
            disabled={submitting}
            sx={{ mt: 3 }}
          >
            {submitting
              ? 'Please wait…'
              : tab === 'login'
                ? 'Log in'
                : 'Create account'}
          </Button>
        </Box>

        <Typography
          variant="body2"
          align="center"
          color="text.secondary"
          sx={{ mt: 2 }}
        >
          {tab === 'login' ? (
            <>
              New here?{' '}
              <Box
                component="span"
                onClick={() => switchTab('signup')}
                sx={{
                  color: 'primary.main',
                  cursor: 'pointer',
                }}
              >
                Create an account
              </Box>
            </>
          ) : (
            <>
              Already registered?{' '}
              <Box
                component="span"
                onClick={() => switchTab('login')}
                sx={{
                  color: 'primary.main',
                  cursor: 'pointer',
                }}
              >
                Log in
              </Box>
            </>
          )}
        </Typography>
      </Paper>
    </Box>
  )
}
