import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// RTL's auto-cleanup also works, but being explicit keeps the
// behavior independent of the `globals` flag.
afterEach(() => {
  cleanup()
})

// recharts' ResponsiveContainer observes its host element; jsdom has
// no ResizeObserver, so stub the smallest surface that keeps the
// chart mount from throwing in tests (the charts still render
// nothing measurable in jsdom — assertions target the surrounding
// UI, never SVG internals).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverStub
}
