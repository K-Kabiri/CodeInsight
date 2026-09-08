import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'

import { CompletenessNote } from './CompletenessNote'
import { FindingsList } from './FindingsList'
import { formatMetricValue } from './format'

/**
 * Per-metric rich views (ticket 05): each metric family renders its
 * persisted `detail` JSON as tables and lists — per-file LOC, per-
 * function complexity, per-class CBO/LCOM/DIT, per-module
 * Instability, dependency cycles, duplication blocks, smells and
 * violations findings. Every renderer is driven by the engine's
 * actual detail shape (pinned by the backend's detail-contract
 * test), never by hard-coded demo data, and `not_applicable`/
 * `partial` metrics show their reason instead of a pretend number.
 */

function SummaryChips({ items }) {
  return (
    <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1.5 }}>
      {items.map(([label, value]) => (
        <Chip
          key={label}
          size="small"
          label={`${label}: ${value ?? '—'}`}
          variant="outlined"
        />
      ))}
    </Box>
  )
}

function DataTable({ columns, rows, emptyLabel }) {
  if (!rows || rows.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        {emptyLabel}
      </Typography>
    )
  }

  return (
    <TableContainer
      component={Paper}
      elevation={0}
      variant="outlined"
      sx={{ borderColor: 'divider' }}
    >
      <Table size="small">
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column.key} sx={{ fontWeight: 700 }}>
                {column.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow key={index} hover>
              {columns.map((column) => (
                <TableCell key={column.key}>
                  {column.render
                    ? column.render(row)
                    : String(row[column.key] ?? '—')}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}

const lineRange = (record) =>
  `${record.lineno ?? '—'}–${record.endline ?? '—'}`

// --- LOC -------------------------------------------------------------

function LocDetail({ detail }) {
  const totals = detail.totals ?? {}

  return (
    <Box>
      <SummaryChips
        items={[
          ['Total LOC', totals.loc],
          ['SLOC', totals.sloc],
          ['Comments', totals.comments],
          ['Blank', totals.blank],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          { key: 'loc', label: 'LOC' },
          { key: 'sloc', label: 'SLOC' },
          { key: 'lloc', label: 'LLOC' },
          { key: 'comments', label: 'Comments' },
          { key: 'blank', label: 'Blank' },
          {
            key: 'comment_ratio',
            label: 'Comment %',
            render: (row) => {
              const ratio = row.comment_ratio
              return ratio === undefined || ratio === null
                ? '—'
                : `${(ratio * 100).toFixed(1)}%`
            },
          },
        ]}
        rows={detail.files ?? []}
        emptyLabel="No files in the detail payload."
      />
    </Box>
  )
}

// --- Complexity (CYCLOMATIC / COGNITIVE) ------------------------------

const complexityColumns = [
  { key: 'name', label: 'Name' },
  { key: 'type', label: 'Type' },
  {
    key: 'complexity',
    label: 'Complexity',
    render: (row) => formatMetricValue(row.complexity, ''),
  },
  {
    key: 'rank',
    label: 'Rank',
    render: (row) => row.rank ?? '—',
  },
  { key: 'lines', label: 'Lines', render: lineRange },
]

function flattenBlocks(detail) {
  const rows = []
  for (const fileResult of detail.files ?? []) {
    for (const block of fileResult.blocks ?? []) {
      rows.push({ ...block, file: fileResult.file })
    }
  }
  return rows
}

function CyclomaticDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total', detail.total],
          ['Average', formatMetricValue(detail.average, '')],
          ['Files', detail.files?.length],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          ...complexityColumns,
        ]}
        rows={flattenBlocks(detail)}
        emptyLabel="No complexity blocks in the detail payload."
      />
    </Box>
  )
}

function flattenFunctions(detail) {
  const rows = []
  for (const fileResult of detail.files ?? []) {
    for (const fn of fileResult.functions ?? []) {
      rows.push({ ...fn, file: fileResult.file })
    }
  }
  return rows
}

function CognitiveDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total', detail.total],
          ['Average', formatMetricValue(detail.average, '')],
          ['Functions', detail.function_count],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          { key: 'name', label: 'Name' },
          { key: 'type', label: 'Type' },
          {
            key: 'complexity',
            label: 'Complexity',
            render: (row) => formatMetricValue(row.complexity, ''),
          },
          {
            key: 'max_nesting',
            label: 'Max nesting',
            render: (row) => row.max_nesting ?? '—',
          },
          { key: 'lines', label: 'Lines', render: lineRange },
        ]}
        rows={flattenFunctions(detail)}
        emptyLabel="No functions in the detail payload."
      />
    </Box>
  )
}

// --- Halstead ---------------------------------------------------------

function HalsteadDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total volume', formatMetricValue(detail.total, '')],
          ['Average', formatMetricValue(detail.average, '')],
          ['Files', detail.files?.length],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          {
            key: 'volume',
            label: 'Volume',
            render: (row) => formatMetricValue(row.volume, ''),
          },
          { key: 'vocabulary', label: 'Vocabulary' },
          { key: 'length', label: 'Length' },
          {
            key: 'difficulty',
            label: 'Difficulty',
            render: (row) => formatMetricValue(row.difficulty, ''),
          },
          {
            key: 'effort',
            label: 'Effort',
            render: (row) => formatMetricValue(row.effort, ''),
          },
        ]}
        rows={detail.files ?? []}
        emptyLabel="No files in the detail payload."
      />
    </Box>
  )
}

// --- Class metrics (CBO / LCOM / DIT) ---------------------------------

function flattenClasses(detail) {
  const rows = []
  for (const fileResult of detail.files ?? []) {
    for (const cls of fileResult.classes ?? []) {
      rows.push({ ...cls, file: fileResult.file })
    }
  }
  return rows
}

function CboDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total', detail.total],
          ['Average', formatMetricValue(detail.average, '')],
          ['Classes', detail.class_count],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          { key: 'name', label: 'Class' },
          { key: 'cbo', label: 'CBO' },
          {
            key: 'coupled_classes',
            label: 'Coupled to',
            render: (row) => row.coupled_classes?.join(', ') || '—',
          },
          { key: 'lines', label: 'Lines', render: lineRange },
        ]}
        rows={flattenClasses(detail)}
        emptyLabel="No classes in the detail payload."
      />
    </Box>
  )
}

function LcomDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total', detail.total],
          ['Average', formatMetricValue(detail.average, '')],
          ['Classes', detail.class_count],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          { key: 'name', label: 'Class' },
          { key: 'lcom', label: 'LCOM' },
          { key: 'p', label: 'P' },
          { key: 'q', label: 'Q' },
          { key: 'method_count', label: 'Methods' },
          { key: 'lines', label: 'Lines', render: lineRange },
        ]}
        rows={flattenClasses(detail)}
        emptyLabel="No classes in the detail payload."
      />
    </Box>
  )
}

function DitDetail({ detail }) {
  return (
    <Box>
      <SummaryChips
        items={[
          ['Total', detail.total],
          ['Average', formatMetricValue(detail.average, '')],
          ['Max', detail.max],
        ]}
      />
      <DataTable
        columns={[
          { key: 'file', label: 'File' },
          { key: 'name', label: 'Class' },
          { key: 'dit', label: 'DIT' },
          {
            key: 'bases',
            label: 'Bases',
            render: (row) => row.bases?.join(', ') || '—',
          },
          {
            key: 'inheritance_path',
            label: 'Path',
            render: (row) =>
              row.inheritance_path?.join(' → ') || '—',
          },
          { key: 'lines', label: 'Lines', render: lineRange },
        ]}
        rows={flattenClasses(detail)}
        emptyLabel="No classes in the detail payload."
      />
    </Box>
  )
}

// --- Instability ------------------------------------------------------

function InstabilityDetail({ detail }) {
  const rows = (detail.files ?? []).map((file) => ({
    ...file,
    i: detail.completeness === 'full' ? file.i : null,
    ca: detail.completeness === 'full' ? file.ca : null,
  }))

  return (
    <Box>
      <SummaryChips
        items={
          detail.completeness === 'full'
            ? [
                ['Average I', formatMetricValue(detail.average, '')],
                ['Modules', detail.totals?.modules],
                ['Ce', detail.totals?.ce],
                ['Ca', detail.totals?.ca],
              ]
            : [['Modules', rows.length]]
        }
      />
      <DataTable
        columns={[
          { key: 'module', label: 'Module' },
          { key: 'ce', label: 'Ce' },
          { key: 'ca', label: 'Ca' },
          {
            key: 'i',
            label: 'I',
            render: (row) => formatMetricValue(row.i, ''),
          },
        ]}
        rows={rows}
        emptyLabel="No modules in the detail payload."
      />
    </Box>
  )
}

// --- Cyclic Dependencies ----------------------------------------------

function CyclicDetail({ detail }) {
  const cycles = detail.cycles ?? []
  const selfLoops = detail.self_loops ?? []

  return (
    <Box>
      <SummaryChips
        items={[['Cycles', cycles.length], ['Self-loops', selfLoops.length]]}
      />

      {cycles.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No dependency cycles found.
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {cycles.map((cycle, index) => (
            <Paper
              key={index}
              elevation={0}
              variant="outlined"
              sx={{
                p: 1,
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                flexWrap: 'wrap',
              }}
            >
              {cycle.map((module, moduleIndex) => (
                <Box
                  key={module}
                  sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                >
                  <Chip size="small" label={module} />
                  {moduleIndex < cycle.length - 1 && (
                    <Typography color="text.secondary">→</Typography>
                  )}
                </Box>
              ))}
            </Paper>
          ))}
        </Box>
      )}

      {selfLoops.length > 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          Self-loops (a module importing itself):{' '}
          {selfLoops.join(', ')}
        </Typography>
      )}
    </Box>
  )
}

// --- Duplication ------------------------------------------------------

/**
 * Each duplicated occurrence is one row; the rows of one clone group
 * are the copies of the same duplicated block, so every row carries
 * group/ordinal/copies ("which copies belong together") plus the
 * explainable entity/kind fields ("what was repeated — a function,
 * a class, a for loop, statements — and in which class when it is a
 * method"). Old persisted details without the new fields degrade to
 * plain file/line rows.
 */
function DuplicationDetail({ detail }) {
  const unattributed = detail.unattributed_files ?? []

  const blockLabel = (row) => {
    if (row.group === undefined || row.group === null) return '—'
    const copies = row.copies ?? '—'
    const ordinal = row.ordinal ?? '—'
    return `#${row.group + 1} · ${ordinal}/${copies}`
  }

  const entityLabel = (row) => {
    if (row.entity) {
      return row.class_name
        ? `${row.entity} · ${row.class_name}`
        : row.entity
    }
    return row.entity_type === 'module' ? 'Module' : '—'
  }

  const kindLabel = (row) => row.kind ?? row.entity_type ?? '—'

  return (
    <Box>
      <SummaryChips
        items={[
          [
            'Duplication',
            detail.density === null || detail.density === undefined
              ? '—'
              : formatMetricValue(detail.density, 'percent'),
          ],
          ['Blocks', detail.duplicated_blocks],
          ['Duplicated lines', detail.duplicated_lines],
          ['Lines', detail.lines_of_code],
        ]}
      />

      {unattributed.length > 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {unattributed.length === 1
            ? `${unattributed[0]} could not be parsed (syntax errors) — the duplicated lines are real, but the function/class each block belongs to cannot be determined.`
            : `${unattributed.length} files could not be parsed (syntax errors) — their duplicated lines are real, but the function/class each block belongs to cannot be determined.`}
        </Typography>
      )}

      <DataTable
        columns={[
          { key: 'block', label: 'Block', render: blockLabel },
          { key: 'file', label: 'File' },
          { key: 'entity', label: 'Entity', render: entityLabel },
          { key: 'kind', label: 'Kind', render: kindLabel },
          {
            key: 'lines',
            label: 'Lines',
            render: (row) => `${row.start_line}–${row.end_line}`,
          },
        ]}
        rows={detail.blocks ?? []}
        emptyLabel="No duplicated blocks."
      />
    </Box>
  )
}

// --- Code Smells ------------------------------------------------------

function CodeSmellsDetail({ detail }) {
  const smells = []
  for (const fileResult of detail.files ?? []) {
    for (const smell of fileResult.smells ?? []) {
      smells.push({ ...smell, file: fileResult.file })
    }
  }

  return (
    <Box>
      <SummaryChips
        items={[
          ['Smells', detail.totals?.smells],
          ['Files', detail.totals?.files],
          ['Types', detail.totals?.types],
        ]}
      />
      {smells.length > 0 && (
        <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1 }}>
          {Object.entries(detail.by_type ?? {}).map(([type, count]) => (
            <Chip
              key={type}
              size="small"
              label={`${type}: ${count}`}
              variant="outlined"
            />
          ))}
        </Box>
      )}
      <FindingsList records={smells} emptyLabel="No smells found." />
    </Box>
  )
}

// --- Rule Violations --------------------------------------------------

function ViolationsDetail({ detail }) {
  const bySeverity = Object.entries(detail.by_severity ?? {})

  return (
    <Box>
      <SummaryChips
        items={[
          ['Violations', detail.totals?.violations],
          ['Files', detail.totals?.files],
          ['Rules', detail.totals?.rules],
        ]}
      />
      {bySeverity.length > 0 && (
        <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1 }}>
          {bySeverity.map(([severity, count]) => (
            <Chip
              key={severity}
              size="small"
              label={`${severity}: ${count}`}
              variant="outlined"
            />
          ))}
        </Box>
      )}
      <FindingsList
        records={detail.violations ?? []}
        emptyLabel="No violations found."
      />
    </Box>
  )
}

// --- Dispatcher -------------------------------------------------------

const FAMILY_RENDERERS = {
  LOC: LocDetail,
  CYCLOMATIC: CyclomaticDetail,
  COGNITIVE: CognitiveDetail,
  Halstead: HalsteadDetail,
  CBO: CboDetail,
  LCOM: LcomDetail,
  DIT: DitDetail,
  INSTABILITY: InstabilityDetail,
  CYCLIC: CyclicDetail,
  DUPLICATION: DuplicationDetail,
  CODE_SMELLS: CodeSmellsDetail,
  VIOLATIONS: ViolationsDetail,
}

/**
 * The results dispatcher: renders one metric's persisted detail. A
 * `not_applicable` metric stops at the reason note; a `partial`
 * metric shows the note above whatever the engine could report;
 * everything else renders the family table/list.
 */
export function MetricDetail({ metric }) {
  const detail = metric?.detail
  if (!detail) return null

  const completeness = detail.completeness
  const FamilyRenderer = FAMILY_RENDERERS[metric.name]

  return (
    <Box>
      <CompletenessNote detail={detail} />
      {completeness !== 'not_applicable' &&
        (FamilyRenderer ? (
          <Box sx={{ mt: 1 }}>
            <FamilyRenderer detail={detail} />
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            No detail renderer for {metric.name}.
          </Typography>
        ))}
    </Box>
  )
}
