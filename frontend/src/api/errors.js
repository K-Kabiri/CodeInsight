/**
 * Pick the first readable message out of a DRF-style error payload so
 * the UI can render it next to the form that failed. Falls back to a
 * generic message when the payload is not what we expect.
 */
export function extractErrorMessage(error) {
  const data = error?.response?.data
  if (!data) return 'Something went wrong. Please try again.'
  const first = (value) => (Array.isArray(value) ? value[0] : value)
  return (
    first(data.non_field_errors) ||
    first(data.username) ||
    first(data.password) ||
    first(data.name) ||
    first(data.source_file) ||
    first(data.metrics) ||
    (typeof data.detail === 'string' ? data.detail : undefined) ||
    'Request failed. Please try again.'
  )
}

export function isNotFound(error) {
  return error?.response?.status === 404
}
