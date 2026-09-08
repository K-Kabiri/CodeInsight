import { QueryClient } from '@tanstack/react-query'
import {
  act,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

const emptyPage = {
  count: 0,
  next: null,
  previous: null,
  results: [],
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
    name: 'VIOLATIONS',
    display_name: 'Rule Violations',
    category: 'Code Health',
    description: 'Ruff and Bandit findings.',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'INSTABILITY',
    display_name: 'Instability',
    category: 'Design Quality',
    description: 'Ce / (Ca + Ce).',
    unit: '',
    higher_is_better: false,
    supports_llm: true,
  },
  {
    name: 'CYCLIC',
    display_name: 'Cyclic Dependencies',
    category: 'Design Quality',
    description: 'Number of dependency cycles between modules.',
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

// ---- Fixture detail payloads (shaped after the backend engines) ----

const locDetail = {
  totals: { loc: 120, lloc: 80, sloc: 70, comments: 12, blank: 10 },
  files: [
    {
      file: 'main.py',
      loc: 60,
      lloc: 40,
      sloc: 35,
      comments: 6,
      single_comments: 4,
      multi: 2,
      blank: 5,
      comment_ratio: 0.1,
    },
    {
      file: 'service.py',
      loc: 60,
      lloc: 40,
      sloc: 35,
      comments: 6,
      single_comments: 4,
      multi: 2,
      blank: 5,
      comment_ratio: 0.1,
    },
  ],
}

const cyclomaticDetail = {
  total: 5,
  average: 2.5,
  files: [
    {
      file: 'service.py',
      total: 5,
      blocks: [
        {
          name: 'handle',
          type: 'function',
          complexity: 3,
          rank: 'B',
          lineno: 10,
          endline: 22,
          classname: null,
        },
        {
          name: 'Service',
          type: 'class',
          complexity: 2,
          rank: 'A',
          lineno: 30,
          endline: 45,
        },
      ],
    },
  ],
}

const codeSmellsDetail = {
  metric: 'CODE_SMELLS',
  scope: 'project',
  completeness: 'full',
  totals: { smells: 2, files: 1, types: 2 },
  by_type: { 'long-method': 1, 'magic-number': 1 },
  files: [
    {
      file: 'service.py',
      parsed: true,
      smells: [
        {
          type: 'long-method',
          lineno: 12,
          endline: 45,
          message: 'Function create_user — 34 lines, max 30.',
          entity: 'create_user',
          entity_type: 'method',
          class_name: 'UserService',
        },
        {
          type: 'magic-number',
          lineno: 60,
          endline: 60,
          message: 'Magic number 86400 used.',
          entity: 'refresh',
          entity_type: 'function',
          class_name: null,
        },
      ],
    },
  ],
}

const violationsDetail = {
  metric: 'VIOLATIONS',
  scope: 'project',
  completeness: 'full',
  totals: { violations: 2, files: 2, rules: 2 },
  by_rule: { E501: 1, B608: 1 },
  by_severity: { error: 2 },
  by_file: { 'config.py': 1, 'db.py': 1 },
  violations: [
    {
      rule: 'E501',
      severity: 'error',
      file: 'config.py',
      line: 8,
      column: 99,
      tool_message: 'Line too long (98 > 88 characters)',
      snippet: 'API_BASE = "https://example.com/very/long/path"',
      tool: 'ruff',
    },
    {
      rule: 'B608',
      severity: 'medium',
      file: 'db.py',
      line: 22,
      column: 4,
      tool_message: 'SQL injection possible with string-built query',
      snippet: 'cursor.execute("SELECT * FROM t WHERE id = " + uid)',
      tool: 'bandit',
    },
  ],
}

const duplicationDetail = {
  metric: 'DUPLICATION',
  scope: 'project',
  completeness: 'full',
  density: 20.0,
  duplicated_blocks: 1,
  duplicated_lines: 28,
  lines_of_code: 140,
  unattributed_files: ['legacy_syntax.py'],
  blocks: [
    {
      file: 'dup_a.py',
      start_line: 10,
      end_line: 23,
      group: 0,
      copies: 2,
      ordinal: 1,
      entity: 'duplicated',
      entity_type: 'function',
      class_name: null,
      kind: 'function',
    },
    {
      file: 'dup_b.py',
      start_line: 4,
      end_line: 17,
      group: 0,
      copies: 2,
      ordinal: 2,
      entity: 'duplicated',
      entity_type: 'function',
      class_name: null,
      kind: 'function',
    },
  ],
}

// ADR-0001 graceful cases: Cyclic Dependencies is not_applicable and
// Instability is partial on a single-file input.
const notApplicableCyclic = {
  metric: 'CYCLIC',
  scope: 'single_file',
  completeness: 'not_applicable',
  reason:
    'Dependency cycles require at least two modules — not applicable to a single-file input.',
  cycles: [],
  self_loops: [],
}

const partialInstability = {
  metric: 'INSTABILITY',
  scope: 'single_file',
  completeness: 'partial',
  reason:
    'Ca (incoming dependents) cannot be observed for a single-file input — only the visible Ce is reported; I is not claimed.',
  files: [
    {
      file: 'main.py',
      module: 'main',
      ce: 2,
      imported_modules: ['os', 'sys'],
    },
  ],
}

const completedAnalysis = {
  id: 7,
  project_version: 10,
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
      detail: locDetail,
    },
    {
      name: 'CYCLOMATIC',
      display_name: 'Cyclomatic Complexity',
      status: 'COMPLETED',
      value: 5,
      execution_time: 0.05,
      error_message: '',
      detail: cyclomaticDetail,
    },
    {
      name: 'CODE_SMELLS',
      display_name: 'Code Smells',
      status: 'COMPLETED',
      value: 2,
      execution_time: 0.03,
      error_message: '',
      detail: codeSmellsDetail,
    },
    {
      name: 'DUPLICATION',
      display_name: 'Duplication',
      status: 'COMPLETED',
      value: 20.0,
      execution_time: 0.03,
      error_message: '',
      detail: duplicationDetail,
    },
    {
      name: 'VIOLATIONS',
      display_name: 'Rule Violations',
      status: 'COMPLETED',
      value: 2,
      execution_time: 0.04,
      error_message: '',
      detail: violationsDetail,
    },
    {
      name: 'INSTABILITY',
      display_name: 'Instability',
      status: 'COMPLETED',
      value: null,
      execution_time: 0.01,
      error_message: '',
      detail: partialInstability,
    },
    {
      name: 'CYCLIC',
      display_name: 'Cyclic Dependencies',
      status: 'COMPLETED',
      value: null,
      execution_time: 0.01,
      error_message: '',
      detail: notApplicableCyclic,
    },
  ],
}

// The display name renders twice per metric: once on the result card,
// once on the detail section header. Return the section Paper (second
// match) so callers wrap it once with within(). Await the name
// itself: the sections render only after the analysis payload arrives.
async function sectionFor(displayName) {
  const main = within(await screen.findByRole('main'))
  const matches = await main.findAllByText(displayName)
  return matches[1].closest('.MuiPaper-root')
}

describe('analyses list', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listMetrics.mockResolvedValue(catalog)
    client.getAnalysis.mockResolvedValue(completedAnalysis)
  })

  it('shows every analysis with status and timestamps', async () => {
    client.listAnalyses.mockResolvedValue({
      count: 3,
      next: null,
      previous: null,
      results: [
        {
          id: 7,
          project_version: 10,
          status: 'COMPLETED',
          started_at: '2026-08-05T10:00:02Z',
          finished_at: '2026-08-05T10:00:08Z',
          created_at: '2026-08-05T10:00:00Z',
          metrics: [],
        },
        {
          id: 8,
          project_version: 10,
          status: 'RUNNING',
          started_at: '2026-08-06T09:00:00Z',
          finished_at: null,
          created_at: '2026-08-06T09:00:00Z',
          metrics: [],
        },
        {
          id: 9,
          project_version: 11,
          status: 'FAILED',
          started_at: '2026-08-04T12:00:00Z',
          finished_at: '2026-08-04T12:00:01Z',
          created_at: '2026-08-04T12:00:00Z',
          metrics: [],
        },
      ],
    })
    renderAt('/analyses')

    expect(await screen.findByText('Analysis #7')).toBeInTheDocument()
    expect(screen.getByText('Analysis #8')).toBeInTheDocument()
    expect(screen.getByText('Analysis #9')).toBeInTheDocument()

    const main = within(screen.getByRole('main'))
    expect(main.getAllByText('COMPLETED').length).toBeGreaterThanOrEqual(1)
    expect(main.getAllByText('RUNNING').length).toBeGreaterThanOrEqual(1)
    expect(main.getAllByText('FAILED').length).toBeGreaterThanOrEqual(1)

    // Timestamps render for created/started/finished.
    expect(main.getAllByText(/2026/).length).toBeGreaterThanOrEqual(3)
  })

  it('opens an analysis from the list', async () => {
    client.listAnalyses.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 7,
          project_version: 10,
          status: 'COMPLETED',
          started_at: '2026-08-05T10:00:02Z',
          finished_at: '2026-08-05T10:00:08Z',
          created_at: '2026-08-05T10:00:00Z',
          metrics: [],
        },
      ],
    })
    const user = userEvent.setup()
    renderAt('/analyses')

    await user.click(await screen.findByText('Analysis #7'))

    await waitFor(() =>
      expect(client.getAnalysis).toHaveBeenCalledWith('7'),
    )
  })

  it('guides an empty list to the projects screen', async () => {
    client.listAnalyses.mockResolvedValue(emptyPage)
    renderAt('/analyses')

    expect(await screen.findByText('No analyses yet')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Go to your projects' }),
    ).toBeInTheDocument()
  })
})

describe('analysis detail with polling', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-1')
    client.listMetrics.mockResolvedValue(catalog)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // Flush pending work under fake timers. The session check and the
  // first query fetch resolve as promises, but TanStack Query v5
  // notifies subscribers via setTimeout(0) — so an empty act() is
  // not enough; advance zero-time timers too. waitFor/findBy* cannot
  // advance vitest fake timers (the installed @testing-library/dom
  // only auto-advances jest's), so the polling test drives timers
  // manually and asserts synchronously.
  async function flush() {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
  }

  it('polls a PENDING analysis until it completes', async () => {
    vi.useFakeTimers()

    const pending = {
      id: 7,
      project_version: 10,
      status: 'PENDING',
      started_at: null,
      finished_at: null,
      created_at: '2026-08-05T10:00:00Z',
      metrics: [],
    }

    client.getAnalysis
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(completedAnalysis)

    renderAt('/analyses/7')

    // First fetch resolves to PENDING; the header chip shows it.
    // The auth check -> shell render -> analysis fetch -> notify is
    // a chain of promise + zero-timer hops, so flush a few times.
    await flush()
    await flush()
    await flush()
    expect(
      screen.getByRole('heading', { name: 'Analysis #7' }),
    ).toBeInTheDocument()
    expect(screen.getByText('PENDING')).toBeInTheDocument()
    expect(screen.getByText(/still running/i)).toBeInTheDocument()
    expect(client.getAnalysis).toHaveBeenCalledTimes(1)

    // Advance past the poll interval; the second fetch returns the
    // completed analysis and polling stops.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500)
    })
    await flush()

    expect(screen.getAllByText('COMPLETED').length).toBeGreaterThan(0)
    expect(client.getAnalysis).toHaveBeenCalledTimes(2)
    expect(
      screen.queryByText(/still running/i),
    ).not.toBeInTheDocument()
  })

  it('renders metric cards with value, unit, status and execution time', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis)
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))

    // Value + unit from the catalog.
    expect(await main.findByText('120')).toBeInTheDocument()
    expect(main.getByText('lines')).toBeInTheDocument()

    // Per-metric status and execution time (sub-second runs render
    // as milliseconds, longer runs as seconds).
    expect(main.getAllByText('COMPLETED').length).toBeGreaterThanOrEqual(6)
    expect(main.getByText(/1\.20s execution/)).toBeInTheDocument()
    expect(main.getByText(/50ms execution/)).toBeInTheDocument()

    // Lower-is-better hint comes from the catalog, but only beside a
    // value that clears the metric's own floor: LOC (120) has no
    // floor, CYCLOMATIC 5 and Duplication 20% meet theirs, while the
    // 2 smells, 2 violations, the partial Instability and the
    // not_applicable Cyclic cards are at/below their floor (or have
    // no value) — so 3 of the 7 cards carry the hint.
    expect(main.getAllByText('Lower is better').length).toBe(3)
  })

  it('hides the direction hint when a completed metric has no meaningful value', async () => {
    // A zero result (no findings, clean code) carries no direction:
    // "Lower is better" beside 0 would be meaningless.
    client.getAnalysis.mockResolvedValue({
      ...completedAnalysis,
      metrics: [
        {
          name: 'CYCLOMATIC',
          display_name: 'Cyclomatic Complexity',
          status: 'COMPLETED',
          value: 0,
          execution_time: 0.05,
          error_message: '',
          detail: cyclomaticDetail,
        },
      ],
    })
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))
    await main.findByText('0')
    expect(main.queryByText('Lower is better')).not.toBeInTheDocument()
  })

  it('applies each metric’s own floor before showing the direction hint', async () => {
    // The floor is per metric because scales differ: 0.35 on the
    // 0–1 Instability scale clears its 0.1 floor, 6 smells clear
    // theirs, while 3% duplication and 2 violations sit below their
    // 5-floor — so only two cards carry the nudge.
    client.getAnalysis.mockResolvedValue({
      ...completedAnalysis,
      metrics: [
        {
          name: 'INSTABILITY',
          display_name: 'Instability',
          status: 'COMPLETED',
          value: 0.35,
          execution_time: 0.01,
          error_message: '',
          detail: { completeness: 'full', average: 0.35, totals: {}, files: [] },
        },
        {
          name: 'DUPLICATION',
          display_name: 'Duplication',
          status: 'COMPLETED',
          value: 3.0,
          execution_time: 0.01,
          error_message: '',
          detail: { density: 3.0, blocks: [] },
        },
        {
          name: 'CODE_SMELLS',
          display_name: 'Code Smells',
          status: 'COMPLETED',
          value: 6,
          execution_time: 0.01,
          error_message: '',
          detail: { totals: { smells: 6 }, files: [], by_type: {} },
        },
        {
          name: 'VIOLATIONS',
          display_name: 'Rule Violations',
          status: 'COMPLETED',
          value: 2,
          execution_time: 0.01,
          error_message: '',
          detail: { totals: { violations: 2 }, by_severity: {}, violations: [] },
        },
      ],
    })
    renderAt('/analyses/7')

    const main = within(await screen.findByRole('main'))
    await main.findByText('0.35')
    expect(main.getAllByText('Lower is better').length).toBe(2)
  })

  it('renders smells with entity, type, message and lines', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis)
    renderAt('/analyses/7')

    const smellsSection = within(await sectionFor('Code Smells'))

    // entity + class_name + type + message + line range.
    expect(
      await smellsSection.findByText('create_user'),
    ).toBeInTheDocument()
    expect(smellsSection.getByText('· UserService')).toBeInTheDocument()
    expect(smellsSection.getByText('long-method: 1')).toBeInTheDocument()
    expect(smellsSection.getByText('magic-number: 1')).toBeInTheDocument()
    expect(
      smellsSection.getByText(/Function create_user — 34 lines/),
    ).toBeInTheDocument()
    expect(smellsSection.getByText('service.py:12–45')).toBeInTheDocument()
  })

  it('renders violations with rule, severity, message and snippet', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis)
    renderAt('/analyses/7')

    const violationsSection = within(await sectionFor('Rule Violations'))

    expect(
      await violationsSection.findByText('E501'),
    ).toBeInTheDocument()
    expect(violationsSection.getByText('B608')).toBeInTheDocument()
    expect(violationsSection.getByText('error: 2')).toBeInTheDocument()
    expect(
      violationsSection.getByText('Line too long (98 > 88 characters)'),
    ).toBeInTheDocument()
    expect(
      violationsSection.getByText(
        'SQL injection possible with string-built query',
      ),
    ).toBeInTheDocument()

    // The offending snippet renders in a code block.
    expect(
      violationsSection.getByText(
        'API_BASE = "https://example.com/very/long/path"',
      ),
    ).toBeInTheDocument()
    expect(
      violationsSection.getByText(
        'cursor.execute("SELECT * FROM t WHERE id = " + uid)',
      ),
    ).toBeInTheDocument()

    // Rule/location evidence.
    expect(violationsSection.getByText('config.py:8')).toBeInTheDocument()
    expect(violationsSection.getByText('db.py:22')).toBeInTheDocument()
  })

  it('renders duplication blocks with entity, kind, copy-group and lines', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis)
    renderAt('/analyses/7')

    const duplicationSection = within(await sectionFor('Duplication'))

    // What was repeated: the whole function `duplicated` — entity
    // and kind on each copy row.
    expect(
      (await duplicationSection.findAllByText('duplicated')).length,
    ).toBe(2)

    // Copies of one clone group are tied together: same block number,
    // distinct ordinal within the pair.
    expect(
      duplicationSection.getByText('#1 · 1/2'),
    ).toBeInTheDocument()
    expect(
      duplicationSection.getByText('#1 · 2/2'),
    ).toBeInTheDocument()
    expect(
      duplicationSection.getAllByText('function').length,
    ).toBe(2)

    // Location evidence for both copies.
    expect(
      duplicationSection.getByText('dup_a.py'),
    ).toBeInTheDocument()
    expect(
      duplicationSection.getByText('10–23'),
    ).toBeInTheDocument()
    expect(
      duplicationSection.getByText('dup_b.py'),
    ).toBeInTheDocument()
    expect(
      duplicationSection.getByText('4–17'),
    ).toBeInTheDocument()

    // A file that could not be parsed is explained, not silently
    // shown with dash entities.
    expect(
      duplicationSection.getByText(
        /legacy_syntax\.py could not be parsed \(syntax errors\)/,
      ),
    ).toBeInTheDocument()
  })

  it('shows not_applicable and partial metrics with their reasons', async () => {
    client.getAnalysis.mockResolvedValue(completedAnalysis)
    renderAt('/analyses/7')

    const cyclicSection = within(await sectionFor('Cyclic Dependencies'))
    expect(
      await cyclicSection.findByText(/Not applicable:/i),
    ).toBeInTheDocument()
    expect(
      cyclicSection.getByText(
        /Dependency cycles require at least two modules/i,
      ),
    ).toBeInTheDocument()

    const instabilitySection = within(await sectionFor('Instability'))
    expect(
      await instabilitySection.findByText(/Partial results:/i),
    ).toBeInTheDocument()
    expect(
      instabilitySection.getByText(/only the visible Ce is reported/i),
    ).toBeInTheDocument()

    // No fabricated scalar: the cards show an em dash, not a number.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  it('shows the analysis failure with per-metric error messages', async () => {
    client.getAnalysis.mockResolvedValue({
      id: 7,
      project_version: 10,
      status: 'FAILED',
      started_at: '2026-08-05T10:00:02Z',
      finished_at: '2026-08-05T10:00:03Z',
      created_at: '2026-08-05T10:00:00Z',
      metrics: [
        {
          name: 'LOC',
          display_name: 'Lines of Code',
          status: 'FAILED',
          value: null,
          execution_time: null,
          error_message: 'Something exploded while analyzing.',
          detail: null,
        },
      ],
    })
    renderAt('/analyses/7')

    expect(
      await screen.findByText(/this analysis failed/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Something exploded while analyzing.'),
    ).toBeInTheDocument()

    // A FAILED metric has no value, so the direction hint is hidden
    // instead of implying the missing number is "better".
    expect(
      screen.queryByText('Lower is better'),
    ).not.toBeInTheDocument()
  })

  it('shows a not-found state for an analysis the user cannot access', async () => {
    client.getAnalysis.mockRejectedValue({
      response: { status: 404, data: { detail: 'Not found.' } },
    })
    renderAt('/analyses/999')

    expect(
      await screen.findByText('Analysis not found'),
    ).toBeInTheDocument()
  })
})
