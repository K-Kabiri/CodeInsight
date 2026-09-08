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
  deleteProject: vi.fn(),
  listVersions: vi.fn(),
  uploadVersion: vi.fn(),
  listMetrics: vi.fn(),
  listAnalyses: vi.fn(),
  createAnalysis: vi.fn(),
  deleteAnalysis: vi.fn(),
}))

const emptyPage = {
  count: 0,
  next: null,
  previous: null,
  results: [],
}

function renderApp(path = '/') {
  window.history.pushState({}, '', path)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

function main() {
  return within(screen.getByRole('main'))
}

// The destructive confirm lives inside the MUI Dialog, so scope the
// lookup there — identical labels may exist behind the overlay.
async function confirmDelete(user, label) {
  const dialog = await screen.findByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: label }))
}

describe('delete flows', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({
      id: 1,
      username: 'alice',
      email: '',
      date_joined: '2026-08-01T00:00:00Z',
    })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listProjects.mockResolvedValue(emptyPage)
    client.listAnalyses.mockResolvedValue(emptyPage)
    client.listMetrics.mockResolvedValue([])
  })

  it('deletes a project from the table after confirmation', async () => {
    const project = {
      id: 7,
      name: 'Doomed Project',
      description: '',
      created_at: '2026-08-01T10:00:00Z',
      updated_at: '2026-08-01T10:00:00Z',
    }
    client.listProjects
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [project],
      })
      .mockResolvedValueOnce(emptyPage)
    client.deleteProject.mockResolvedValue({})
    const user = userEvent.setup()
    renderApp('/')

    expect(await screen.findByText('Doomed Project')).toBeInTheDocument()

    await user.click(
      main().getByRole('button', {
        name: 'Delete project Doomed Project',
      }),
    )
    expect(
      screen.getByRole('heading', { name: 'Delete project?' }),
    ).toBeInTheDocument()
    await confirmDelete(user, 'Delete project')

    await waitFor(() =>
      expect(client.deleteProject).toHaveBeenCalledWith(7),
    )
    await waitFor(() =>
      expect(screen.queryByText('Doomed Project')).not.toBeInTheDocument(),
    )
  })

  it('deletes a settled analysis from the list but not an in-flight one', async () => {
    client.listAnalyses.mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 12,
          status: 'COMPLETED',
          created_at: '2026-08-01T10:00:00Z',
          started_at: '2026-08-01T10:00:01Z',
          finished_at: '2026-08-01T10:00:03Z',
        },
        {
          id: 13,
          status: 'RUNNING',
          created_at: '2026-08-02T10:00:00Z',
          started_at: '2026-08-02T10:00:00Z',
          finished_at: null,
        },
      ],
    })
    client.listAnalyses.mockResolvedValue(emptyPage)
    client.deleteAnalysis.mockResolvedValue({})
    const user = userEvent.setup()
    renderApp('/analyses')

    expect(await screen.findByText('Analysis #12')).toBeInTheDocument()
    expect(screen.getByText('Analysis #13')).toBeInTheDocument()

    // In-flight runs carry a disabled delete action (a click can
    // never open the confirmation for it).
    const runningDelete = screen.getByRole('button', {
      name: 'Delete analysis #13',
    })
    expect(runningDelete).toBeDisabled()
    expect(
      screen.queryByRole('heading', { name: 'Delete analysis?' }),
    ).not.toBeInTheDocument()

    // A settled run opens the confirmation and is deleted.
    await user.click(
      screen.getByRole('button', {
        name: 'Delete analysis #12',
      }),
    )
    expect(
      screen.getByRole('heading', { name: 'Delete analysis?' }),
    ).toBeInTheDocument()
    await confirmDelete(user, 'Delete analysis')

    await waitFor(() =>
      expect(client.deleteAnalysis).toHaveBeenCalledWith(12),
    )
    await waitFor(() =>
      expect(screen.queryByText('Analysis #12')).not.toBeInTheDocument(),
    )
  })

  it('deletes the current project from its own screen and goes home', async () => {
    const project = {
      id: 9,
      name: 'My Project',
      description: 'desc',
      created_at: '2026-08-01T10:00:00Z',
      updated_at: '2026-08-01T10:00:00Z',
    }
    client.getProject.mockResolvedValue(project)
    client.listVersions.mockResolvedValue(emptyPage)
    client.deleteProject.mockResolvedValue({})
    const user = userEvent.setup()
    renderApp('/projects/9')

    expect(
      await screen.findByRole('heading', { name: 'My Project' }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Delete project' }),
    )
    expect(
      screen.getByRole('heading', { name: 'Delete project?' }),
    ).toBeInTheDocument()
    await confirmDelete(user, 'Delete project')

    await waitFor(() =>
      expect(client.deleteProject).toHaveBeenCalledWith('9'),
    )
    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }),
    ).toBeInTheDocument()
  })
})
