import { QueryClient } from '@tanstack/react-query'
import {
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

function kpiValue(label) {
  // The sidebar also shows labels like "Analyses", so scope the KPI
  // lookup to the main content area.
  const mainArea = within(screen.getByRole('main'))
  const labelElement = mainArea.getByText(label)
  const card = labelElement.closest('.MuiPaper-root')
  return within(card).getByRole('heading', { level: 4 })
}

function main() {
  return within(screen.getByRole('main'))
}

const emptyPage = {
  count: 0,
  next: null,
  previous: null,
  results: [],
}

describe('dashboard (prototype-A layout)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    window.history.pushState({}, '', '/')
    client.fetchMe.mockResolvedValue({
      id: 1,
      username: 'alice',
      email: 'alice@example.com',
      date_joined: '2026-08-01T00:00:00Z',
    })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listProjects.mockResolvedValue(emptyPage)
    client.listAnalyses.mockResolvedValue(emptyPage)
    client.listMetrics.mockResolvedValue([])
  })

  it('renders the prototype-A blocks: KPIs, profile, activity and table', async () => {
    client.listProjects.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 1,
          name: 'Alpha',
          description: 'first project',
          created_at: '2026-08-01T10:00:00Z',
          updated_at: '2026-08-01T10:00:00Z',
        },
        {
          id: 2,
          name: 'Beta',
          description: '',
          created_at: '2026-08-02T10:00:00Z',
          updated_at: '2026-08-02T10:00:00Z',
        },
      ],
    })
    client.listAnalyses.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 11,
          status: 'COMPLETED',
          created_at: '2026-08-15T10:00:00Z',
          metrics: [
            { name: 'INSTABILITY', value: 0.5, detail: { average: 0.5 } },
            { name: 'LOC', value: 120, status: 'COMPLETED' },
          ],
        },
        {
          id: 12,
          status: 'COMPLETED',
          created_at: '2026-08-16T10:00:00Z',
          metrics: [
            { name: 'INSTABILITY', value: 0.3, detail: { average: 0.3 } },
            { name: 'LOC', value: 80, status: 'COMPLETED' },
          ],
        },
      ],
    })
    renderDashboard()

    // Projects table rows.
    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()

    // Two KPI cards aggregate the mocked data.
    expect(kpiValue('Total projects')).toHaveTextContent('2')
    expect(kpiValue('Total analyses')).toHaveTextContent('2')

    // The A-layout cards: profile (with the signed-in user and his
    // membership date), the 7-day activity chart and the recent
    // analyses list.
    expect(main().getByText('Profile')).toBeInTheDocument()
    expect(main().getByText(/member since/i)).toBeInTheDocument()
    expect(main().queryByText('Metrics available')).not.toBeInTheDocument()
    expect(main().getByTestId('activity-chart')).toBeInTheDocument()
    expect(main().getByText('Analysis #11')).toBeInTheDocument()
    expect(main().getByText('Analysis #12')).toBeInTheDocument()
  })

  it('aggregates analyses across multiple pages', async () => {
    client.listProjects.mockResolvedValue(emptyPage)
    client.listAnalyses
      .mockResolvedValueOnce({
        count: 2,
        next: '/api/analyses/?page=2',
        previous: null,
        results: [
          {
            id: 11,
            status: 'COMPLETED',
            created_at: '2026-08-15T10:00:00Z',
            metrics: [
              { name: 'INSTABILITY', value: 0.6, detail: { average: 0.6 } },
            ],
          },
        ],
      })
      .mockResolvedValueOnce({
        count: 2,
        next: null,
        previous: '/api/analyses/?page=1',
        results: [
          {
            id: 12,
            status: 'COMPLETED',
            created_at: '2026-08-16T10:00:00Z',
            metrics: [],
          },
        ],
      })
    renderDashboard()

    expect(await screen.findByText('No projects yet')).toBeInTheDocument()
    await waitFor(() =>
      expect(kpiValue('Total analyses')).toHaveTextContent('2'),
    )
  })

  it('guides a first-time user with an empty state', async () => {
    renderDashboard()

    expect(
      await screen.findByText('No projects yet'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /create your first project/i,
      }),
    ).toBeInTheDocument()
  })

  it('creates a project, closes the dialog and opens the new project', async () => {
    const created = {
      id: 9,
      name: 'New Proj',
      description: 'd',
      created_at: '2026-08-03T10:00:00Z',
      updated_at: '2026-08-03T10:00:00Z',
    }
    // The redirect lands on /projects/9, which fetches the project
    // and its (empty) versions list.
    client.createProject.mockResolvedValue(created)
    client.getProject.mockResolvedValue(created)
    client.listVersions.mockResolvedValue(emptyPage)
    const user = userEvent.setup()
    renderDashboard()

    await user.click(
      await within(await screen.findByRole('main')).findByRole(
        'button',
        { name: 'New project' },
      ),
    )

    await user.type(await screen.findByLabelText(/name/i), 'New Proj')
    await user.type(
      await screen.findByLabelText(/description/i),
      'd',
    )
    await user.click(
      await screen.findByRole('button', { name: 'Create' }),
    )

    await waitFor(() =>
      expect(client.createProject).toHaveBeenCalledWith({
        name: 'New Proj',
        description: 'd',
      }),
    )
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    // The user lands on the freshly created project's screen.
    expect(
      await screen.findByRole('heading', { name: 'New Proj' }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/projects/9')
  })

  it('shows the backend error when creating a project fails', async () => {
    client.createProject.mockRejectedValue({
      response: { data: { name: ['This field is required.'] } },
    })
    const user = userEvent.setup()
    renderDashboard()

    await user.click(
      await within(await screen.findByRole('main')).findByRole(
        'button',
        { name: 'New project' },
      ),
    )
    await user.type(await screen.findByLabelText(/name/i), 'X')
    await user.click(
      await screen.findByRole('button', { name: 'Create' }),
    )

    expect(
      await screen.findByText('This field is required.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('opens the new-project dialog from the sidebar quick action', async () => {
    const user = userEvent.setup()
    renderDashboard()

    // Both the sidebar quick action and the projects table's own
    // button are labelled "New project"; the sidebar item renders
    // first.
    const newProjectButtons = await screen.findAllByRole('button', {
      name: 'New project',
    })
    expect(newProjectButtons).toHaveLength(2)
    await user.click(newProjectButtons[0])

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    // MUI unmounts the dialog after its exit transition, so wait.
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
  })

  it('pages through the projects table', async () => {
    client.listProjects.mockResolvedValueOnce({
      count: 25,
      next: '/api/projects/?page=2',
      previous: null,
      results: Array.from({ length: 20 }, (_, index) => ({
        id: index + 1,
        name: `Project ${index + 1}`,
        description: '',
        created_at: '2026-08-01T10:00:00Z',
        updated_at: '2026-08-01T10:00:00Z',
      })),
    })
    const user = userEvent.setup()
    renderDashboard()

    expect(await screen.findByText('Project 1')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() =>
      expect(client.listProjects).toHaveBeenCalledWith({ page: 2 }),
    )
  })
})
