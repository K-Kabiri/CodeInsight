import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'

import {
  createAnalysis,
  createProject,
  deleteAnalysis,
  deleteProject,
  generateAiReport,
  getAiReport,
  getAnalysis,
  getProject,
  listAnalyses,
  listMetrics,
  listProjects,
  listVersions,
  uploadVersion,
} from './client'
import { isNotFound } from './errors'

// Safety net for the dashboard's analyses walk and the versions walk:
// never loop forever if the backend misbehaves.
const MAX_ANALYSIS_PAGES = 100
const MAX_VERSION_PAGES = 100

export function pageFromUrl(url) {
  if (!url) return null
  const page = new URL(url, window.location.origin).searchParams.get('page')
  return page ? Number(page) : null
}

// --- projects --------------------------------------------------------

export function useProjects(page = 1) {
  return useQuery({
    queryKey: ['projects', 'page', page],
    queryFn: () => listProjects({ page }),
  })
}

export function useProject(projectId) {
  return useQuery({
    queryKey: ['projects', 'detail', projectId],
    queryFn: () => getProject(projectId),
    enabled: Boolean(projectId),
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    // Wrap so the API function receives exactly the payload: TanStack
    // Query v5 calls mutationFn with (variables, context), and the
    // context object must not leak into the API client seam.
    mutationFn: (payload) => createProject(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (projectId) => deleteProject(projectId),
    onSuccess: () => {
      // Removing a project also removes its versions and analyses, so
      // every aggregate and list that could mention it must refresh.
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

// --- versions --------------------------------------------------------

export function useVersions(projectId) {
  return useQuery({
    queryKey: ['projects', projectId, 'versions'],
    // The backend pages versions at 20, newest first; walk every page
    // so the whole history is available (a later ticket picks a
    // version to analyze from this list). Same pattern as the
    // dashboard's analyses walk.
    queryFn: async () => {
      const versions = []
      let page = 1
      let hasNext = true

      while (hasNext && page <= MAX_VERSION_PAGES) {
        const response = await listVersions(projectId, { page })
        versions.push(...(response.results ?? []))
        hasNext = Boolean(response.next)
        page += 1
      }

      return versions
    },
    enabled: Boolean(projectId),
  })
}

export function useUploadVersion(projectId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file) => uploadVersion(projectId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'versions'],
      })
    },
  })
}

// --- metric catalog --------------------------------------------------

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: listMetrics,
  })
}

// --- analyses ---------------------------------------------------------

export function useProjectAnalyses(projectId) {
  const versionsQuery = useVersions(projectId)

  // The backend's only Analyses filter is by project *version*
  // (?project_version=<version id>), never by project. The project
  // screen's history is therefore the union of every version's
  // Analyses, walked version by version and merged newest first.
  // (The previous implementation passed the project id as
  // project_version, which 404s against the real backend — the
  // filter resolves a ProjectVersion pk, not a project.)
  const versionIds = (versionsQuery.data ?? [])
    .map((version) => version.id)
    .join(',')

  return useQuery({
    queryKey: ['projects', projectId, 'analyses', versionIds],
    queryFn: async () => {
      const analyses = []
      for (const version of versionsQuery.data ?? []) {
        let page = 1
        let hasNext = true

        while (hasNext && page <= MAX_ANALYSIS_PAGES) {
          const response = await listAnalyses({
            project_version: version.id,
            page,
          })
          analyses.push(...(response.results ?? []))
          hasNext = Boolean(response.next)
          page += 1
        }
      }

      return analyses.sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at),
      )
    },
    enabled: Boolean(projectId) && versionsQuery.isSuccess,
  })
}

// One version's full Analysis history (the version-comparison screen
// fetches each side with ?project_version=<version id>, newest first,
// then picks the newest COMPLETED run as that side's outcome).
export function useVersionAnalyses(versionId) {
  return useQuery({
    queryKey: ['projects', 'version', versionId, 'analyses'],
    queryFn: async () => {
      const analyses = []
      let page = 1
      let hasNext = true

      while (hasNext && page <= MAX_ANALYSIS_PAGES) {
        const response = await listAnalyses({
          project_version: versionId,
          page,
        })
        analyses.push(...(response.results ?? []))
        hasNext = Boolean(response.next)
        page += 1
      }

      return analyses
    },
    enabled: Boolean(versionId),
  })
}

export function useCreateAnalysis(projectId) {
  const queryClient = useQueryClient()
  return useMutation({
    // Wrap so the API function receives exactly the payload: TanStack
    // Query v5 calls mutationFn with (variables, context), and the
    // context object must not leak into the API client seam.
    mutationFn: (payload) => createAnalysis(payload),
    onSuccess: () => {
      // The created Analysis shows up in the project's own history,
      // the global list, and the dashboard's aggregate numbers.
      queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'analyses'],
      })
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

// Deleting one Analysis touches the same surfaces creation does: the
// global list, every per-project history (they key under ['projects',
// ..., 'analyses']), and the dashboard aggregates.
export function useDeleteAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (analysisId) => deleteAnalysis(analysisId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

// The Analysis detail polls while the run is in flight and stops
// the moment it settles — the lifecycle is PENDING -> RUNNING ->
// COMPLETED/FAILED, and the backend persists every transition, so
// refetching is the whole polling story (no websockets, no timers
// in components — frontend spec: "a detail whose status is
// PENDING/RUNNING uses refetchInterval polling until
// COMPLETED/FAILED").
const ANALYSIS_POLL_INTERVAL_MS = 2000

export function useAnalysis(analysisId) {
  return useQuery({
    queryKey: ['analyses', 'detail', analysisId],
    queryFn: () => getAnalysis(analysisId),
    enabled: Boolean(analysisId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PENDING' || status === 'RUNNING'
        ? ANALYSIS_POLL_INTERVAL_MS
        : false
    },
    // Keep polling even while the tab is in the background: the user
    // may switch away while the analysis runs and should still see
    // the completed result when they come back.
    refetchIntervalInBackground: true,
  })
}

// The global Analyses list (sidebar "Analyses"): the backend pages
// at 20, newest first. One page at a time with Previous/Next, like
// the dashboard projects table.
export function useAnalyses(page = 1) {
  return useQuery({
    queryKey: ['analyses', 'page', page],
    queryFn: () => listAnalyses({ page }),
  })
}

// --- AI report (ai-report ticket 05) -----------------------------------

// The stored AI report for a COMPLETED Analysis that asked for AI.
// Fetching starts only when the Analysis is COMPLETED and
// ai_requested is on (the report is written before the run flips to
// COMPLETED, so a single fetch at completion is enough — no extra
// polling). A 404 simply means "never generated" (the LLM call
// failed during the run): it resolves to null so the UI can offer
// the retry state instead of an error screen.
export function useAiReport(analysisId, enabled = false) {
  return useQuery({
    queryKey: ['analyses', analysisId, 'ai-report'],
    queryFn: async () => {
      try {
        return await getAiReport(analysisId)
      } catch (error) {
        if (isNotFound(error)) return null
        throw error
      }
    },
    enabled: Boolean(analysisId) && Boolean(enabled),
  })
}

// The retry/regenerate action behind "AI report unavailable" and the
// summary's "Regenerate report": POSTs a synchronous generation and
// puts the fresh report straight into the read-back query's cache.
export function useGenerateAiReport(analysisId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => generateAiReport(analysisId),
    onSuccess: (report) => {
      queryClient.setQueryData(
        ['analyses', analysisId, 'ai-report'],
        report,
      )
    },
  })
}

// --- dashboard -------------------------------------------------------
/**
 * The dashboard's key numbers: total analyses and the aggregate
 * instability / smells / lines across all of the user's analyses. The
 * analyses list response already carries every metric's value and
 * detail, so the whole set is walked page by page and summarized
 * here — no backend changes needed (frontend spec: consume the API
 * as-is). The last-7-days activity buckets and recent-window count
 * come from each Analysis's created_at.
 */
const DAY_MS = 24 * 60 * 60 * 1000

function summarizeAnalyses(analyses) {
  const instability = []
  let totalSmells = 0
  let linesAnalyzed = 0
  let analysesThisWeek = 0

  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const activity = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(startOfToday)
    day.setDate(day.getDate() - (6 - index))
    return {
      start: day.getTime(),
      label: day.toLocaleDateString('en-US', { weekday: 'short' }),
      count: 0,
    }
  })

  const now = Date.now()
  const weekAgo = now - 7 * DAY_MS

  for (const analysis of analyses) {
    const created = analysis.created_at
      ? new Date(analysis.created_at).getTime()
      : NaN

    if (!Number.isNaN(created)) {
      if (created >= weekAgo) {
        analysesThisWeek += 1
      }
      const index = activity.findIndex(
        (bucket) =>
          created >= bucket.start && created < bucket.start + DAY_MS,
      )
      if (index !== -1) {
        activity[index].count += 1
      }
    }

    for (const metric of analysis.metrics ?? []) {
      if (metric.name === 'INSTABILITY') {
        const average = metric.detail?.average ?? metric.value
        if (typeof average === 'number') {
          instability.push(average)
        }
      }
      if (metric.name === 'CODE_SMELLS') {
        totalSmells += metric.detail?.totals?.smells ?? 0
      }
      if (metric.name === 'LOC' && typeof metric.value === 'number') {
        linesAnalyzed += metric.value
      }
    }
  }

  return {
    analysesCount: analyses.length,
    avgInstability: instability.length
      ? instability.reduce((sum, value) => sum + value, 0) /
        instability.length
      : null,
    totalSmells,
    linesAnalyzed,
    analysesThisWeek,
    activity: activity.map(({ label, count }) => ({ label, count })),
    // The walked list stays newest-first (the backend orders by
    // -created_at and pages ascend), so the dashboard can slice its
    // "recent analyses" card straight off the top.
    analyses,
  }
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const analyses = []
      let page = 1
      let hasNext = true

      while (hasNext && page <= MAX_ANALYSIS_PAGES) {
        const response = await listAnalyses({ page })
        analyses.push(...(response.results ?? []))
        hasNext = Boolean(response.next)
        page += 1
      }

      return summarizeAnalyses(analyses)
    },
  })
}
