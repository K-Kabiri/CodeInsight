import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { NewProjectProvider } from './components/NewProjectDialog'
import { theme } from './theme'

const defaultQueryClient = new QueryClient()

/**
 * The provider stack shared by the real entry point (main.jsx) and
 * the test renderer — tests pass a fresh QueryClient so cached state
 * never leaks between cases.
 */
export default function AppProviders({
  children,
  queryClient = defaultQueryClient,
}) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AuthProvider>
            <NewProjectProvider>{children}</NewProjectProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
