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
  getAiReport: vi.fn(),
  generateAiReport: vi.fn(),
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
]

const locDetail = {
  totals: { loc: 120, lloc: 80, sloc: 70, comments: 12, blank: 10 },
  files: [
    {
      file: 'main.py',
      loc: 120,
      lloc: 80,
      sloc: 70,
      comments: 12,
      blank: 10,
      comment_ratio: 0.1,
    },
  ],
}

function completedAnalysis({ aiRequested }) {
  return {
    id: 7,
    project_version: 10,
    status: 'COMPLETED',
    started_at: '2026-08-05T10:00:02Z',
    finished_at: '2026-08-05T10:00:08Z',
    created_at: '2026-08-05T10:00:00Z',
    ai_requested: aiRequested,
    metrics: [
      {
        name: 'LOC',
        display_name: 'Lines of Code',
        status: 'COMPLETED',
        value: 120,
        execution_time: 1.2,
        error_message: '',
        detail: locDetail,
      },
    ],
  }
}

// Shaped after AIReportSerializer output (GET/POST
// /api/analyses/{id}/ai-report/).
const report = {
  summary: 'The codebase is compact and well organised.',
  metric_content: {
    LOC: {
      explanation: 'The file is small and focused.',
      suggestions: [
        'Extract helper functions.',
        'Keep it under 200 lines.',
      ],
    },
  },
  model_name: 'glm-4.5-flash',
  generated_at: '2026-08-05T10:00:09Z',
}

// The display name renders twice per metric: once on the result card,
// once on the detail section header. Return the section Paper (second
// match) so callers wrap it once with within().
async function sectionFor(displayName) {
  const main = within(await screen.findByRole('main'))
  const matches = await main.findAllByText(displayName)
  return matches[1].closest('.MuiPaper-root')
}

describe('AI report on the results screen', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listMetrics.mockResolvedValue(catalog)
  })

  it('renders the summary box and per-metric explanations beside the real numbers', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis({ aiRequested: true }))
    client.getAiReport.mockResolvedValue(report)
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))

    // Overall summary box at the top with its model attribution.
    expect(
      await main.findByText('The codebase is compact and well organised.'),
    ).toBeInTheDocument()
    expect(main.getByText('AI summary')).toBeInTheDocument()
    expect(main.getByText(/glm-4\.5-flash/)).toBeInTheDocument()
    expect(
      main.getByRole('button', { name: 'Regenerate report' }),
    ).toBeInTheDocument()

    // Per-metric explanation + suggestions under the metric's detail.
    const locSection = within(await sectionFor('Lines of Code'))
    expect(
      await locSection.findByText('AI explanation'),
    ).toBeInTheDocument()
    expect(
      locSection.getByText('The file is small and focused.'),
    ).toBeInTheDocument()
    expect(
      locSection.getByText('Extract helper functions.'),
    ).toBeInTheDocument()
    expect(
      locSection.getByText('Keep it under 200 lines.'),
    ).toBeInTheDocument()

    // The real numbers are untouched by the AI content.
    expect(main.getAllByText('120').length).toBeGreaterThanOrEqual(1)
    expect(main.getAllByText('lines').length).toBeGreaterThanOrEqual(1)
    expect(main.queryByText('AI report unavailable')).not.toBeInTheDocument()
  })

  it('shows "AI report unavailable" with a retry that generates the report', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis({ aiRequested: true }))
    client.getAiReport.mockRejectedValue({
      response: { status: 404, data: { detail: 'Not found.' } },
    })
    client.generateAiReport.mockResolvedValue(report)
    const user = userEvent.setup()
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))
    expect(
      await main.findByText('AI report unavailable'),
    ).toBeInTheDocument()

    // The metric results render regardless.
    expect(main.getAllByText('120').length).toBeGreaterThanOrEqual(1)

    await user.click(main.getByRole('button', { name: 'Retry' }))

    await waitFor(() =>
      expect(client.generateAiReport).toHaveBeenCalledWith('7'),
    )
    expect(
      await main.findByText('The codebase is compact and well organised.'),
    ).toBeInTheDocument()
    expect(main.queryByText('AI report unavailable')).not.toBeInTheDocument()
  })

  it('regenerates the whole report from the summary box', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis({ aiRequested: true }))
    client.getAiReport.mockResolvedValue(report)
    client.generateAiReport.mockResolvedValue({
      ...report,
      summary: 'A regenerated take on the codebase.',
    })
    const user = userEvent.setup()
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))
    expect(
      await main.findByText('The codebase is compact and well organised.'),
    ).toBeInTheDocument()

    await user.click(
      main.getByRole('button', { name: 'Regenerate report' }),
    )

    await waitFor(() =>
      expect(client.generateAiReport).toHaveBeenCalledWith('7'),
    )
    expect(
      await main.findByText('A regenerated take on the codebase.'),
    ).toBeInTheDocument()
    expect(
      main.queryByText('The codebase is compact and well organised.'),
    ).not.toBeInTheDocument()
  })

  it('shows no AI section when the analysis did not request AI', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis({ aiRequested: false }))
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))

    // The metric results still render (card + detail section).
    expect(
      (await main.findAllByText('Lines of Code')).length,
    ).toBeGreaterThanOrEqual(2)
    expect(main.getAllByText('120').length).toBeGreaterThanOrEqual(1)

    expect(main.queryByText('AI summary')).not.toBeInTheDocument()
    expect(
      main.queryByText('AI report unavailable'),
    ).not.toBeInTheDocument()
    expect(client.getAiReport).not.toHaveBeenCalled()
  })

  it('surfaces a failed regeneration inline without hiding the old report or metrics', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis({ aiRequested: true }))
    client.getAiReport.mockResolvedValue(report)
    client.generateAiReport.mockRejectedValue({
      response: { status: 503, data: { detail: 'Provider timed out.' } },
    })
    const user = userEvent.setup()
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))
    expect(
      await main.findByText('The codebase is compact and well organised.'),
    ).toBeInTheDocument()

    await user.click(
      main.getByRole('button', { name: 'Regenerate report' }),
    )

    // The error surfaces inline; the stored summary and numbers stay.
    expect(await main.findByText('Provider timed out.')).toBeInTheDocument()
    expect(
      main.getByText('The codebase is compact and well organised.'),
    ).toBeInTheDocument()
    expect(main.getAllByText('120').length).toBeGreaterThanOrEqual(1)
  })
})
