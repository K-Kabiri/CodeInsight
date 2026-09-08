import { QueryClient } from '@tanstack/react-query'
import {
  render,
  screen,
  waitFor,
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

function renderAtProject(projectId = 1) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  window.history.pushState({}, '', `/projects/${projectId}`)
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

const project = {
  id: 1,
  name: 'Alpha',
  description: 'first project',
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

const emptyVersions = {
  count: 0,
  next: null,
  previous: null,
  results: [],
}

describe('project detail', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.getProject.mockResolvedValue(project)
    client.listVersions.mockResolvedValue(emptyVersions)
    // The project screen lists the project's own analyses too, and
    // the analysis dialog's catalog query resolves if it is opened.
    client.listAnalyses.mockResolvedValue(emptyVersions)
    client.listMetrics.mockResolvedValue([])
  })

  it('shows the project and its uploaded versions', async () => {
    client.listVersions.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 10,
          version_number: 1,
          source_file: '/media/projects/alpha_v1.py',
          uploaded_at: '2026-08-01T10:00:00Z',
        },
        {
          id: 11,
          version_number: 2,
          source_file: '/media/projects/alpha_v2.zip',
          uploaded_at: '2026-08-02T10:00:00Z',
        },
      ],
    })
    renderAtProject()

    expect(
      await screen.findByRole('heading', { name: 'Alpha' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Version 1')).toBeInTheDocument()
    expect(screen.getByText('alpha_v1.py')).toBeInTheDocument()
    expect(screen.getByText('Version 2')).toBeInTheDocument()
    expect(screen.getByText('alpha_v2.zip')).toBeInTheDocument()
  })

  it('uploads a chosen file as the next version', async () => {
    client.uploadVersion.mockResolvedValue({
      id: 12,
      version_number: 1,
      source_file: '/media/projects/main.py',
      uploaded_at: '2026-08-03T10:00:00Z',
    })
    const file = new File(['print(1)\n'], 'main.py', {
      type: 'text/x-python',
    })
    const user = userEvent.setup()
    renderAtProject()

    await screen.findByRole('heading', { name: 'Alpha' })

    await user.upload(
      screen.getByLabelText('Upload source file'),
      file,
    )
    await user.click(
      screen.getByRole('button', { name: 'Upload version' }),
    )

    expect(
      await screen.findByText(/uploaded main\.py as version 1/i),
    ).toBeInTheDocument()
    expect(client.uploadVersion).toHaveBeenCalledWith('1', file)
    // The versions list is invalidated and refetched after upload.
    await waitFor(() =>
      expect(client.listVersions.mock.calls.length).toBeGreaterThanOrEqual(
        2,
      ),
    )
  })

  it('surfaces the backend error for a rejected upload', async () => {
    client.uploadVersion.mockRejectedValue({
      response: {
        data: {
          source_file: [
            'File extension "xyz" is not allowed. Allowed extensions are: py, zip.',
          ],
        },
      },
    })
    // A .py file passes the chooser's accept filter; the backend (and
    // its error message) is what rejects the upload here.
    const file = new File(['print(1)\n'], 'main.py', {
      type: 'text/x-python',
    })
    const user = userEvent.setup()
    renderAtProject()

    await screen.findByRole('heading', { name: 'Alpha' })
    await user.upload(
      screen.getByLabelText('Upload source file'),
      file,
    )
    await user.click(
      await screen.findByRole('button', { name: 'Upload version' }),
    )

    expect(await screen.findByText(/not allowed/i)).toBeInTheDocument()
  })

  it('does not accept files outside .py and .zip', async () => {
    const file = new File(['hello'], 'notes.txt', { type: 'text/plain' })
    const user = userEvent.setup()
    renderAtProject()

    await screen.findByRole('heading', { name: 'Alpha' })
    await user.upload(
      screen.getByLabelText('Upload source file'),
      file,
    )
    await user.click(
      screen.getByRole('button', { name: 'Upload version' }),
    )

    expect(
      await screen.findByText(
        /choose a \.py or \.zip file to upload first/i,
      ),
    ).toBeInTheDocument()
    expect(client.uploadVersion).not.toHaveBeenCalled()
  })

  it('rejects an upload attempt without a chosen file', async () => {
    const user = userEvent.setup()
    renderAtProject()

    await screen.findByRole('heading', { name: 'Alpha' })
    await user.click(
      screen.getByRole('button', { name: 'Upload version' }),
    )

    expect(
      await screen.findByText(/choose a \.py or \.zip file to upload first/i),
    ).toBeInTheDocument()
    expect(client.uploadVersion).not.toHaveBeenCalled()
  })

  it('shows a not-found state for a project the user cannot access', async () => {
    client.getProject.mockRejectedValue({
      response: { status: 404, data: { detail: 'Not found.' } },
    })
    renderAtProject(99)

    expect(
      await screen.findByText('Project not found'),
    ).toBeInTheDocument()
  })

  it('fetches the project history per version id, not the project id', async () => {
    // Two versions; the project's Analyses history is the union of
    // each version's Analyses via ?project_version=<version id> —
    // never the project id (that filter resolves a version pk).
    client.listVersions.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 11,
          version_number: 2,
          source_file: '/media/projects/alpha_v2.zip',
          uploaded_at: '2026-08-02T10:00:00Z',
        },
        {
          id: 10,
          version_number: 1,
          source_file: '/media/projects/alpha_v1.py',
          uploaded_at: '2026-08-01T10:00:00Z',
        },
      ],
    })
    client.listAnalyses.mockImplementation((params) =>
      Promise.resolve({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            // Distinct ids per version, like the real backend.
            id: Number(params.project_version) === 10 ? 7 : 8,
            project_version: Number(params.project_version),
            status: 'COMPLETED',
            created_at: '2026-08-05T10:00:00Z',
            metrics: [],
          },
        ],
      }),
    )

    renderAtProject()

    await screen.findByRole('heading', { name: 'Alpha' })

    await waitFor(() =>
      expect(client.listAnalyses).toHaveBeenCalledWith({
        project_version: 10,
        page: 1,
      }),
    )
    await waitFor(() =>
      expect(client.listAnalyses).toHaveBeenCalledWith({
        project_version: 11,
        page: 1,
      }),
    )

    // Both versions' analyses show in the merged history.
    expect(await screen.findByText('Analysis #7')).toBeInTheDocument()
    expect(screen.getByText('Analysis #8')).toBeInTheDocument()
  })
})
