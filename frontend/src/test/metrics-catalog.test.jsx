import { QueryClient } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
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

const CATALOG = [
  {
    name: 'LOC',
    display_name: 'Lines of Code',
    category: 'Complexity & Size',
    description: 'Source lines of code.',
    unit: 'lines',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CYCLOMATIC',
    display_name: 'Cyclomatic Complexity',
    category: 'Complexity & Size',
    description: 'Independent paths through the code.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'INSTABILITY',
    display_name: 'Instability',
    category: 'Design Quality',
    description: 'Efferent / (afferent + efferent).',
    unit: '',
    higher_is_better: false,
    supports_llm: false,
  },
]

function renderCatalog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

describe('metric catalog page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    window.history.pushState({}, '', '/metrics')
    client.fetchMe.mockResolvedValue({
      id: 1,
      username: 'alice',
      email: '',
      date_joined: '2026-08-01T00:00:00Z',
    })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listProjects.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    client.listAnalyses.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    client.listMetrics.mockResolvedValue(CATALOG)
  })

  it('groups the catalog by category with names, units and hints', async () => {
    renderCatalog()

    expect(
      await screen.findByRole('heading', { name: 'Metric catalog' }),
    ).toBeInTheDocument()

    // Wait for the catalog fetch, then assert its content.
    expect(await screen.findByText('Lines of Code')).toBeInTheDocument()
    expect(
      screen.getByText('3 metrics · each documented'),
    ).toBeInTheDocument()

    // Group headers.
    expect(screen.getByText('Complexity & Size')).toBeInTheDocument()
    expect(screen.getByText('Design Quality')).toBeInTheDocument()

    // Metric cards carry display + canonical name, unit and hint.
    const locCard = screen
      .getByText('Lines of Code')
      .closest('.MuiPaper-root')
    expect(within(locCard).getByText('LOC')).toBeInTheDocument()
    expect(within(locCard).getByText('lines')).toBeInTheDocument()
    expect(
      within(locCard).getByText('Lower is better'),
    ).toBeInTheDocument()
    expect(
      within(locCard).getByText('AI-explained'),
    ).toBeInTheDocument()
  })

  it('falls back to a readable empty state without data', async () => {
    client.listMetrics.mockResolvedValue([])
    renderCatalog()

    expect(
      await screen.findByText('Catalog unavailable'),
    ).toBeInTheDocument()
  })
})
