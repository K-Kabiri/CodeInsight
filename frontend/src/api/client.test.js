import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  onRequest,
  onResponseError,
  setUnauthorizedHandler,
} from './client'
import { getToken, setToken } from '../auth/storage'

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    setUnauthorizedHandler(null)
    vi.restoreAllMocks()
  })

  it('attaches the stored token to every request', () => {
    setToken('secret-token')
    const config = onRequest({ headers: {} })
    expect(config.headers.Authorization).toBe('Token secret-token')
  })

  it('leaves requests without a stored token untouched', () => {
    const config = onRequest({ headers: {} })
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('clears the session and fires the handler on a 401', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    setToken('secret-token')

    const error = { response: { status: 401 } }
    await expect(onResponseError(error)).rejects.toBe(error)

    expect(handler).toHaveBeenCalledTimes(1)
    expect(getToken()).toBeNull()
  })

  it('does not treat other error statuses as a lost session', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    setToken('secret-token')

    const error = { response: { status: 400 } }
    await expect(onResponseError(error)).rejects.toBe(error)

    expect(handler).not.toHaveBeenCalled()
    expect(getToken()).toBe('secret-token')
  })
})
