import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// RTL's auto-cleanup also works, but being explicit keeps the
// behavior independent of the `globals` flag.
afterEach(() => {
  cleanup()
})
