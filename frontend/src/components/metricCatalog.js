/**
 * Catalog helpers shared by the metric picker (New Analysis dialog)
 * and the standalone catalog page: grouping by category preserves the
 * backend's first-seen order, and the direction hint mirrors the
 * seeded higher_is_better flag.
 */

export function groupMetricsByCategory(metrics) {
  const groups = []
  const byCategory = new Map()

  for (const metric of metrics) {
    if (!byCategory.has(metric.category)) {
      const group = { category: metric.category, metrics: [] }
      byCategory.set(metric.category, group)
      groups.push(group)
    }
    byCategory.get(metric.category).metrics.push(metric)
  }

  return groups
}

export function directionHint(metric) {
  if (metric.higher_is_better === undefined) return null
  return metric.higher_is_better ? 'Higher is better' : 'Lower is better'
}

export const CATEGORY_ACCENT = {
  'Complexity & Size': '#6ea8ff',
  'Design Quality': '#b07cff',
  'Code Health': '#5ee6c8',
}

export const DEFAULT_CATEGORY_ACCENT = '#6c8cff'

export function categoryAccent(category) {
  return CATEGORY_ACCENT[category] ?? DEFAULT_CATEGORY_ACCENT
}
