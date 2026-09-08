import { QueryClient } from '@tanstack/react-query'
import {
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TOKEN_KEY } from '../auth/storage'
import App from '../App'
import AppProviders from '../AppProviders'
import * as client from '../api/client'

vi.mock('../api/client', () => ({
  api: {},
  setUnauthorizedHandler: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  fetchMe: vi.fn(),
  listProjects: vi.fn(),
  getProject: vi.fn(),
  createProject: vi.fn(),
  listVersions: vi.fn(),
  uploadVersion: vi.fn(),
  listMetrics: vi.fn(),
  listAnalyses: vi.fn(),
  createAnalysis: vi.fn(),
}))

const TWO_METRICS = [
  { name: 'LOC', display_name: 'Lines of Code', category: 'c', unit: 'lines' },
  { name: 'CBO', display_name: 'Coupling', category: 'c', unit: '' },
]

function renderProfile() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

// Scope lookups to the routed page: the sidebar (aside) also shows
// labels like "Projects" and "Profile".
function main() {
  return within(screen.getByRole('main'))
}

function statValue(label) {
  const mainArea = main()
  const labelElement = mainArea.getByText(label)
  const card = labelElement.closest('.MuiPaper-root')
  return within(card).getByRole('heading', { level: 5 })
}

describe('profile page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    window.history.pushState({}, '', '/profile')
    client.fetchMe.mockResolvedValue({
      id: 1,
      username: 'alice',
      email: 'alice@example.com',
      date_joined: '2026-08-01T00:00:00Z',
    })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listProjects.mockResolvedValue({
      count: 3,
      next: null,
      previous: null,
      results: [],
    })
    client.listMetrics.mockResolvedValue(TWO_METRICS)
    client.listAnalyses.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 11,
          status: 'COMPLETED',
          created_at: '2026-08-15T10:00:00Z',
          metrics: [
            { name: 'LOC', value: 500, status: 'COMPLETED' },
            { name: 'INSTABILITY', value: 0.5, detail: { average: 0.5 } },
          ],
        },
      ],
    })
  })

  it('shows the account summary and the user aggregates', async () => {
    renderProfile()

    expect(
      await screen.findByRole('heading', { name: 'Profile' }),
    ).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText(/member since/i)).toBeInTheDocument()

    // Aggregates from the list endpoints (settle after their fetches).
    await waitFor(() =>
      expect(statValue('Metrics available')).toHaveTextContent('2'),
    )
    expect(statValue('Projects')).toHaveTextContent('3')
    expect(statValue('Analyses')).toHaveTextContent('1')
    // The three boxes are the only aggregates on the profile screen.
    expect(screen.queryByText('Lines analyzed')).not.toBeInTheDocument()
    expect(screen.queryByText('Avg instability')).not.toBeInTheDocument()
  })

  it('survives a legacy /me/ payload without a date or email', async () => {
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    renderProfile()

    expect(
      await screen.findByRole('heading', { name: 'Profile' }),
    ).toBeInTheDocument()
    // No email is collected at sign-up, so no fake email is shown.
    expect(screen.queryByText('No email set')).not.toBeInTheDocument()
    expect(screen.queryByText('alice@example.com')).not.toBeInTheDocument()
    expect(screen.getByText(/member since/i)).toBeInTheDocument()
    await waitFor(() =>
      expect(statValue('Metrics available')).toHaveTextContent('2'),
    )
    expect(statValue('Projects')).toHaveTextContent('3')
    expect(statValue('Analyses')).toHaveTextContent('1')
  })
})
