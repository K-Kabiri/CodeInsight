import { Navigate, Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './layouts/AppShell'
import ComingSoon from './pages/ComingSoon'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'

/**
 * Route map (frontend spec): /login is public; everything else lives
 * behind the authenticated shell. Unauthenticated visitors are
 * redirected to the login page by RequireAuth.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route
          path="/projects"
          element={<ComingSoon title="Projects" />}
        />
        <Route
          path="/analyses"
          element={<ComingSoon title="Analyses" />}
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
