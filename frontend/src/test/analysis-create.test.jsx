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

function renderProject(projectId = 1) {
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

const versionsPage = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 10,
      version_number: 2,
      source_file: '/media/projects/alpha_v2.zip',
      uploaded_at: '2026-08-02T10:00:00Z',
    },
    {
      id: 11,
      version_number: 1,
      source_file: '/media/projects/alpha_v1.py',
      uploaded_at: '2026-08-01T10:00:00Z',
    },
  ],
}

const emptyPage = {
  count: 0,
  next: null,
  previous: null,
  results: [],
}

// Shaped after MetricDefinitionSerializer output (GET /api/metrics/).
const catalog = [
  {
    name: 'LOC',
    display_name: 'Lines of Code',
    category: 'Complexity & Size',
    description:
      'Source lines of code per Radon raw metric, reported per file.',
    unit: 'lines',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CYCLOMATIC',
    display_name: 'Cyclomatic Complexity',
    category: 'Complexity & Size',
    description:
      'McCabe cyclomatic complexity: independent paths through each function.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'COGNITIVE',
    display_name: 'Cognitive Complexity',
    category: 'Complexity & Size',
    description: 'SonarSource cognitive complexity of the control flow.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CBO',
    display_name: 'Coupling Between Object Classes',
    category: 'Design Quality',
    description: 'Distinct project classes a class couples to.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'INSTABILITY',
    display_name: 'Instability',
    category: 'Design Quality',
    description: 'Ce / (Ca + Ce) — how likely a module is to ripple.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'DUPLICATION',
    display_name: 'Duplication',
    category: 'Code Health',
    description: 'Percentage of duplicated code, token-based.',
    unit: 'percent',
    higher_is_better: false,
    supports_llm: false,
  },
]

const pendingAnalysis = {
  id: 7,
  project_version: 10,
  status: 'PENDING',
  started_at: null,
  finished_at: null,
  created_at: '2026-08-05T10:00:00Z',
  metrics: [],
}

async function openNewAnalysisDialog(user) {
  await screen.findByRole('heading', { name: 'Alpha' })
  await user.click(screen.getByRole('button', { name: 'New analysis' }))
  await screen.findByRole('dialog')
  // The dialog mounts before the catalog finishes loading; wait for a
  // metric row before interacting with the checkboxes.
  await screen.findByRole('checkbox', { name: 'Select Lines of Code' })
}

describe('analysis creation with metric selection', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.getProject.mockResolvedValue(project)
    client.listVersions.mockResolvedValue(versionsPage)
    client.listAnalyses.mockResolvedValue(emptyPage)
    client.listMetrics.mockResolvedValue(catalog)
  })

  it('loads the metric catalog grouped by category with descriptions', async () => {
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    expect(await screen.findByText('Complexity & Size')).toBeInTheDocument()
    expect(screen.getByText('Design Quality')).toBeInTheDocument()
    expect(screen.getByText('Code Health')).toBeInTheDocument()

    // Descriptions, units and direction hints render per metric.
    expect(
      screen.getByText(/source lines of code per radon raw metric/i),
    ).toBeInTheDocument()
    expect(screen.getByText('lines')).toBeInTheDocument()
    expect(screen.getByText('percent')).toBeInTheDocument()
    expect(
      screen.getAllByText('Lower is better').length,
    ).toBeGreaterThanOrEqual(3)

    // The version to analyze is preselected (newest first).
    expect(screen.getByRole('radio', { name: 'Version 2' })).toBeChecked()
    expect(screen.getByText('0 of 6 selected')).toBeInTheDocument()

    // The catalog is longer than the visible list: the dialog says so
    // and shows the count, so nobody thinks the visible rows are all
    // the metrics there are.
    expect(
      screen.getByText(/all 6 metrics are listed below in 3 groups/i),
    ).toBeInTheDocument()

    // AI explanations default on (ai-report ticket 05).
    expect(
      screen.getByRole('checkbox', { name: 'AI explanations' }),
    ).toBeChecked()
  })

  it('creates an analysis with the chosen version and canonical metric names', async () => {
    client.createAnalysis.mockResolvedValue(pendingAnalysis)
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select Lines of Code' }),
    )
    await user.click(
      screen.getByRole('checkbox', {
        name: 'Select Cyclomatic Complexity',
      }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    await waitFor(() =>
      expect(client.createAnalysis).toHaveBeenCalledWith({
        project_version: '10',
        metrics: ['LOC', 'CYCLOMATIC'],
        ai_requested: true,
      }),
    )

    // The dialog closes and the project page confirms the creation.
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(
      await screen.findByText(/Analysis #7 created/i),
    ).toBeInTheDocument()
  })

  it('blocks creation when no metrics are selected', async () => {
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    // The validation error appears as a top-of-screen modal, not an
    // inline alert at the bottom of the dialog.
    const errorModal = await screen.findByRole('alertdialog')
    expect(
      within(errorModal).getByText(/select at least one metric/i),
    ).toBeInTheDocument()
    expect(client.createAnalysis).not.toHaveBeenCalled()

    // Acknowledging the modal closes it and leaves the form usable.
    await user.click(within(errorModal).getByRole('button', { name: 'OK' }))
    await waitFor(() =>
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('surfaces the backend message when creating fails', async () => {
    client.createAnalysis.mockRejectedValue({
      response: {
        data: {
          metrics: ['At least one metric must be selected.'],
        },
      },
    })
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select Instability' }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    const errorModal = await screen.findByRole('alertdialog')
    expect(
      within(errorModal).getByText(/at least one metric must be selected/i),
    ).toBeInTheDocument()
  })

  it('shows the created analysis with PENDING status in the project history', async () => {
    client.createAnalysis.mockResolvedValue(pendingAnalysis)
    // The project history walks each version via ?project_version=;
    // only version 10 has the new analysis (version 11 has none).
    client.listAnalyses.mockImplementation((params) =>
      Promise.resolve(
        String(params.project_version) === '10'
          ? {
              count: 1,
              next: null,
              previous: null,
              results: [pendingAnalysis],
            }
          : emptyPage,
      ),
    )
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select Lines of Code' }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    expect(await screen.findByText('Analysis #7')).toBeInTheDocument()
    expect(screen.getAllByText('PENDING').length).toBeGreaterThanOrEqual(1)
    expect(
      screen.getByText(/Analysis #7 created/i),
    ).toBeInTheDocument()
  })

  it('selects and clears a whole category with its select-all checkbox', async () => {
    client.createAnalysis.mockResolvedValue(pendingAnalysis)
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    await user.click(
      screen.getByRole('checkbox', { name: 'Select all Complexity & Size' }),
    )
    expect(screen.getByText('3 of 6 selected')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    await waitFor(() =>
      expect(client.createAnalysis).toHaveBeenCalledWith({
        project_version: '10',
        metrics: ['LOC', 'CYCLOMATIC', 'COGNITIVE'],
        ai_requested: true,
      }),
    )
  })

  it('sends ai_requested false when AI explanations is switched off', async () => {
    client.createAnalysis.mockResolvedValue(pendingAnalysis)
    const user = userEvent.setup()
    renderProject()
    await openNewAnalysisDialog(user)

    const aiCheckbox = screen.getByRole('checkbox', {
      name: 'AI explanations',
    })
    await user.click(aiCheckbox)
    expect(aiCheckbox).not.toBeChecked()

    await user.click(
      screen.getByRole('checkbox', { name: 'Select Lines of Code' }),
    )
    await user.click(
      screen.getByRole('button', { name: 'Create analysis' }),
    )

    await waitFor(() =>
      expect(client.createAnalysis).toHaveBeenCalledWith({
        project_version: '10',
        metrics: ['LOC'],
        ai_requested: false,
      }),
    )
  })
})
