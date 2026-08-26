import { useQueryClient } from '@tanstack/react-query'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import {
  fetchMe,
  login as apiLogin,
  register as apiRegister,
  setUnauthorizedHandler,
} from '../api/client'
import { AuthContext } from './context'
import { clearToken, getToken, setToken } from './storage'

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState({
    token: getToken(),
    user: null,
  })
  // A stored token starts in 'loading' until /me/ confirms it;
  // otherwise the visitor is 'anonymous' from the start.
  const [status, setStatus] = useState(() =>
    getToken() ? 'loading' : 'anonymous',
  )

  // Bootstrap: a stored token is confirmed against /me/ so the
  // session survives a page reload. A rejected token lands back on
  // anonymous.
  useEffect(() => {
    const token = getToken()
    if (!token) return undefined

    let cancelled = false
    fetchMe()
      .then((user) => {
        if (!cancelled) {
          setSession({ token, user })
          setStatus('authenticated')
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearToken()
          setSession({ token: null, user: null })
          setStatus('anonymous')
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  // The API client's 401 escape hatch: any protected call that comes
  // back 401 ends the session in place (no full page reload); the
  // guard on protected routes then redirects to the login page.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken()
      setSession({ token: null, user: null })
      setStatus('anonymous')
      queryClient.clear()
    })
  }, [queryClient])

  const login = useCallback(async (username, password) => {
    const { token } = await apiLogin(username, password)
    setToken(token)
    const user = await fetchMe()
    setSession({ token, user })
    setStatus('authenticated')
    return user
  }, [])

  const register = useCallback(async (username, password) => {
    const { token } = await apiRegister(username, password)
    setToken(token)
    const user = await fetchMe()
    setSession({ token, user })
    setStatus('authenticated')
    return user
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setSession({ token: null, user: null })
    setStatus('anonymous')
    queryClient.clear()
  }, [queryClient])

  const value = useMemo(
    () => ({
      session,
      status,
      user: session.user,
      login,
      register,
      logout,
    }),
    [session, status, login, register, logout],
  )

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
