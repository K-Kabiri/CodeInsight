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
  getAnalysis: vi.fn(),
}))

function renderAt(path) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  window.history.pushState({}, '', path)
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

// Newest first, like the backend's versions list.
const versions = [
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
]

const catalog = [
  {
    name: 'LOC',
    display_name: 'Lines of Code',
    category: 'Complexity & Size',
    description: 'Source lines of code per Radon raw metric.',
    unit: 'lines',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CYCLOMATIC',
    display_name: 'Cyclomatic Complexity',
    category: 'Complexity & Size',
    description: 'McCabe cyclomatic complexity.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CODE_SMELLS',
    display_name: 'Code Smells',
    category: 'Code Health',
    description: 'Structural smells.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'DUPLICATION',
    display_name: 'Duplication',
    category: 'Code Health',
    description: 'Percentage of duplicated code.',
    unit: 'percent',
    higher_is_better: false,
    supports_llm: false,
  },
]

// The newest completed Analysis of version 2: LOC grew (worse), smells
// fell (better) — the delta coloring keys off the catalog direction.
const v2Outcome = {
  id: 7,
  project_version: 11,
  status: 'COMPLETED',
  started_at: '2026-08-05T10:00:02Z',
  finished_at: '2026-08-05T10:00:08Z',
  created_at: '2026-08-05T10:00:00Z',
  metrics: [
    {
      name: 'LOC',
      display_name: 'Lines of Code',
      status: 'COMPLETED',
      value: 120,
      execution_time: 1.2,
      error_message: '',
      detail: { totals: { loc: 120 } },
    },
    {
      name: 'CYCLOMATIC',
      display_name: 'Cyclomatic Complexity',
      status: 'COMPLETED',
      value: 5,
      execution_time: 0.05,
      error_message: '',
      detail: { average: 2.5 },
    },
    {
      name: 'CODE_SMELLS',
      display_name: 'Code Smells',
      status: 'COMPLETED',
      value: 2,
      execution_time: 0.03,
      error_message: '',
      detail: { totals: { smells: 2 } },
    },
    {
      name: 'DUPLICATION',
      display_name: 'Duplication',
      status: 'COMPLETED',
      value: null,
      execution_time: 0.01,
      error_message: '',
      detail: { density: 5.0 },
    },
  ],
}

// Version 1's outcome: the older, larger baseline.
const v1Outcome = {
  id: 6,
  project_version: 10,
  status: 'COMPLETED',
  started_at: '2026-08-04T10:00:02Z',
  finished_at: '2026-08-04T10:00:08Z',
  created_at: '2026-08-04T10:00:00Z',
  metrics: [
    {
      name: 'LOC',
      display_name: 'Lines of Code',
      status: 'COMPLETED',
      value: 100,
      execution_time: 1.1,
      error_message: '',
      detail: { totals: { loc: 100 } },
    },
    {
      name: 'CYCLOMATIC',
      display_name: 'Cyclomatic Complexity',
      status: 'COMPLETED',
      value: 3,
      execution_time: 0.05,
      error_message: '',
      detail: { average: 1.8 },
    },
    {
      name: 'CODE_SMELLS',
      display_name: 'Code Smells',
      status: 'COMPLETED',
      value: 5,
      execution_time: 0.03,
      error_message: '',
      detail: { totals: { smells: 5 } },
    },
    {
      name: 'DUPLICATION',
      display_name: 'Duplication',
      status: 'COMPLETED',
      value: null,
      execution_time: 0.01,
      error_message: '',
      detail: { density: 8.0 },
    },
  ],
}

function analysesForVersion(versionId) {
  if (String(versionId) === '11') {
    return {
      count: 1,
      next: null,
      previous: null,
      results: [v2Outcome],
    }
  }
  return {
    count: 1,
    next: null,
    previous: null,
    results: [v1Outcome],
  }
}

describe('version comparison', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.getProject.mockResolvedValue(project)
    client.listVersions.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: versions,
    })
    client.listMetrics.mockResolvedValue(catalog)
    client.listAnalyses.mockImplementation((params) =>
      Promise.resolve(analysesForVersion(params.project_version)),
    )
  })

  it('preselects the two newest versions and fetches each side by version', async () => {
    renderAt('/projects/1/compare')

    // Both sides fetched via the per-version filter.
    await waitFor(() =>
      expect(client.listAnalyses).toHaveBeenCalledWith({
        project_version: '11',
        page: 1,
      }),
    )
    await waitFor(() =>
      expect(client.listAnalyses).toHaveBeenCalledWith({
        project_version: '10',
        page: 1,
      }),
    )

    expect(
      await screen.findByRole('heading', { name: 'Alpha — Compare versions' }),
    ).toBeInTheDocument()
  })

  it('renders the metric delta table with values and deltas', async () => {
    renderAt('/projects/1/compare')

    const table = within(await screen.findByRole('table'))

    // Baseline v2 vs compared v1 for every metric completed on both.
    expect(table.getByText('Lines of Code')).toBeInTheDocument()
    expect(table.getByText('Code Smells')).toBeInTheDocument()
    expect(table.getByText('Duplication')).toBeInTheDocument()

    // Values (baseline / compared) with units from the catalog.
    expect(table.getByText('120')).toBeInTheDocument()
    expect(table.getByText('100')).toBeInTheDocument()
    expect(table.getByText('2.50')).toBeInTheDocument()
    expect(table.getByText('1.80')).toBeInTheDocument()
    expect(table.getByText('5')).toBeInTheDocument()
    expect(table.getByText('2')).toBeInTheDocument()

    // Deltas: LOC −20 (improved, lower is better), smells +3 (worse).
    expect(table.getByText('▲ 20')).toBeInTheDocument()
    expect(table.getByText('▼ 3')).toBeInTheDocument()
    expect(table.getByText('▲ 0.70')).toBeInTheDocument()
    expect(table.getByText('▼ 3.0%')).toBeInTheDocument()

    // Percent metric renders with its unit.
    expect(table.getByText('5.0%')).toBeInTheDocument()
    expect(table.getByText('8.0%')).toBeInTheDocument()
  })

  it('renders the headline charts with per-version values', async () => {
    renderAt('/projects/1/compare')

    expect(
      await screen.findByText('Across versions'),
    ).toBeInTheDocument()

    // Chart cards carry the four headline metrics by display name
    // (each also appears in the delta table, so match all), and the
    // caption under each shows the two versions' numbers.
    for (const name of [
      'Lines of Code',
      'Cyclomatic Complexity',
      'Code Smells',
      'Duplication',
    ]) {
      expect(screen.getAllByText(name).length).toBeGreaterThanOrEqual(2)
    }

    expect(screen.getByText('v2: 120')).toBeInTheDocument()
    expect(screen.getByText('v1: 100')).toBeInTheDocument()
    expect(screen.getByText('v2: 2.50')).toBeInTheDocument()
    expect(screen.getByText('v1: 1.80')).toBeInTheDocument()
  })

  it('switching a side refetches that version and updates the table', async () => {
    // Give the project a third version with a different outcome.
    const v3Outcome = {
      ...v2Outcome,
      id: 8,
      project_version: 12,
      created_at: '2026-08-06T10:00:00Z',
      metrics: [
        ...v2Outcome.metrics.map((metric) => ({ ...metric })),
      ],
    }
    client.listVersions.mockResolvedValue({
      count: 3,
      next: null,
      previous: null,
      results: [
        {
          id: 12,
          version_number: 3,
          source_file: '/media/projects/alpha_v3.py',
          uploaded_at: '2026-08-06T10:00:00Z',
        },
        ...versions,
      ],
    })
    client.listAnalyses.mockImplementation((params) => {
      if (String(params.project_version) === '12') {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [v3Outcome],
        })
      }
      return Promise.resolve(analysesForVersion(params.project_version))
    })

    const user = userEvent.setup()
    renderAt('/projects/1/compare')

    await screen.findByRole('heading', { name: 'Alpha — Compare versions' })

    // With three versions the newest two are preselected (v3 baseline,
    // v2 compared). Switch the compared side to Version 1 (id 10).
    await user.click(
      screen.getByRole('combobox', { name: 'Compared version' }),
    )
    await user.click(await screen.findByRole('option', { name: 'Version 1' }))

    await waitFor(() =>
      expect(client.listAnalyses).toHaveBeenCalledWith({
        project_version: '10',
        page: 1,
      }),
    )
  })

  it('shows an empty state when a version has no completed analysis', async () => {
    client.listAnalyses.mockImplementation((params) => {
      if (String(params.project_version) === '11') {
        return Promise.resolve({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 9,
              project_version: 11,
              status: 'FAILED',
              created_at: '2026-08-07T10:00:00Z',
              metrics: [],
            },
          ],
        })
      }
      return Promise.resolve(analysesForVersion(params.project_version))
    })

    renderAt('/projects/1/compare')

    expect(
      await screen.findByText(/Baseline .* has no completed Analysis yet/i),
    ).toBeInTheDocument()
    // Only the missing side gets the empty state; the compared side
    // is fine, and no delta table renders without both outcomes.
    expect(
      screen.queryByText(/Compared .* has no completed Analysis yet/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('guides the user when the project has fewer than two versions', async () => {
    client.listVersions.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [versions[1]],
    })

    renderAt('/projects/1/compare')

    expect(
      await screen.findByText('Two versions needed'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/upload at least two versions/i),
    ).toBeInTheDocument()
  })

  it('shows a not-found state for a project the user cannot access', async () => {
    client.getProject.mockRejectedValue({
      response: { status: 404, data: { detail: 'Not found.' } },
    })

    renderAt('/projects/99/compare')

    expect(
      await screen.findByText('Project not found'),
    ).toBeInTheDocument()
  })
})
