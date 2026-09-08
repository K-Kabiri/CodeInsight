import { Navigate, Route, Routes } from 'react-router-dom'

import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './layouts/AppShell'
import AnalysesPage from './pages/AnalysesPage'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import MetricCatalogPage from './pages/MetricCatalogPage'
import ProfilePage from './pages/ProfilePage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import ProjectsPage from './pages/ProjectsPage'
import VersionComparePage from './pages/VersionComparePage'

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
          path="/projects"
          element={<ProjectsPage />}
        />
        <Route
          path="/projects/:id"
          element={<ProjectDetailPage />}
        />
        <Route
          path="/projects/:id/compare"
          element={<VersionComparePage />}
        />
        <Route
          path="/analyses"
          element={<AnalysesPage />}
        />
        <Route
          path="/analyses/:id"
          element={<AnalysisDetailPage />}
        />
        <Route
          path="/metrics"
          element={<MetricCatalogPage />}
        />
        <Route
          path="/profile"
          element={<ProfilePage />}
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
