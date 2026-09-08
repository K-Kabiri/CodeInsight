import { Box, Chip, Paper, Typography } from '@mui/material'

import { formatFindingLocation } from './format'

/**
 * The generic findings renderer for the explainable-detail
 * convention (frontend spec): any finding record that carries
 * location + entity evidence renders uniformly — Code Smells
 * (entity/entity_type/class_name/type/message/lineno/endline),
 * Rule Violations (rule/severity/tool_message/snippet/line), and
 * any future engine that follows the same shape. The renderer never
 * hard-codes a metric name; new findings render without new
 * components.
 */
export function FindingsList({ records, emptyLabel = 'No findings.' }) {
  if (!records || records.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        {emptyLabel}
      </Typography>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
      {records.map((record, index) => {
        const title = record.entity ?? record.rule ?? 'Finding'
        const kind =
          record.entity_type ??
          record.type ??
          record.severity ??
          record.tool
        const message = record.message ?? record.tool_message
        const location = formatFindingLocation(record)

        return (
          <Paper
            key={`${title}-${index}`}
            elevation={0}
            sx={{
              p: 1.5,
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: 1,
                flexWrap: 'wrap',
              }}
            >
              <Typography
                variant="body2"
                sx={{ fontWeight: 700, wordBreak: 'break-word' }}
              >
                {title}
                {record.class_name && (
                  <Typography
                    component="span"
                    color="text.secondary"
                    sx={{ fontWeight: 400 }}
                  >
                    {' '}
                    · {record.class_name}
                  </Typography>
                )}
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                {kind && <Chip size="small" label={kind} />}
                <Typography variant="caption" color="text.secondary">
                  {location}
                </Typography>
              </Box>
            </Box>

            {message && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {message}
              </Typography>
            )}

            {record.snippet && (
              <Box
                component="pre"
                sx={{
                  m: 0,
                  mt: 1,
                  p: 1,
                  borderRadius: 1,
                  bgcolor: 'background.default',
                  border: '1px solid',
                  borderColor: 'divider',
                  fontSize: '0.75rem',
                  lineHeight: 1.5,
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {record.snippet}
              </Box>
            )}
          </Paper>
        )
      })}
    </Box>
  )
}
