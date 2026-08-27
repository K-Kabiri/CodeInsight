import { Navigate, Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './layouts/AppShell'
import ComingSoon from './pages/ComingSoon'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import ProjectDetailPage from './pages/ProjectDetailPage'

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
        <Route path="/" element={<DashboardPage />} />
        <Route
          path="/projects/:id"
          element={<ProjectDetailPage />}
        />
        <Route
          path="/projects"
          element={<Navigate to="/" replace />}
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
