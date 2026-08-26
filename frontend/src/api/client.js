import axios from 'axios'

import { clearToken, getToken } from '../auth/storage'

// The single module that talks to the backend (frontend spec: "the
// API client is a single axios module"). UI tests mock this whole
// module, so every screen-level test exercises the seam and never
// the network.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
})

// React wires this up (AuthProvider) so a 401 mid-session flips the
// app back to anonymous instead of a hard page reload. Falls back to
// a full redirect when nothing is registered.
let unauthorizedHandler = null

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

export function onRequest(config) {
  const token = getToken()
  if (token) {
    config.headers = {
      ...config.headers,
      Authorization: `Token ${token}`,
    }
  }
  return config
}

export function onResponseError(error) {
  if (error.response && error.response.status === 401) {
    clearToken()
    if (unauthorizedHandler) {
      unauthorizedHandler()
    } else if (typeof window !== 'undefined') {
      window.location.assign('/login')
    }
  }
  return Promise.reject(error)
}

api.interceptors.request.use(onRequest)
api.interceptors.response.use((response) => response, onResponseError)

// --- auth endpoints -------------------------------------------------

export async function login(username, password) {
  const { data } = await api.post('/auth/token/', { username, password })
  return data // { token }
}

export async function register(username, password) {
  const { data } = await api.post('/auth/register/', { username, password })
  return data // { token }
}

export async function fetchMe() {
  const { data } = await api.get('/me/')
  return data // { id, username }
}

export default api
