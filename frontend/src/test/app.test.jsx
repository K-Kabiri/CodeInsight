import { QueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TOKEN_KEY } from '../auth/storage'
import App from '../App'
import AppProviders from '../AppProviders'
import * as client from '../api/client'

// The single seam: every test mocks the API client module, so no
// test touches the network (frontend spec's testing decision).
vi.mock('../api/client', () => ({
  api: {},
  setUnauthorizedHandler: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  fetchMe: vi.fn(),
}))

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <AppProviders queryClient={queryClient}>
      <App />
    </AppProviders>,
  )
}

describe('app shell and authentication', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    window.history.pushState({}, '', '/')
  })

  it('shows the landing page as the initial screen', () => {
    renderApp()

    expect(
      screen.getByRole('heading', {
        name: /know exactly how your python code quality evolves/i,
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Sign up' })).toBeInTheDocument()
  })

  it('redirects unauthenticated visitors to the login page', async () => {
    renderApp()

    expect(
      await screen.findByRole('tab', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })

  it('logs in and reaches the protected home screen', async () => {
    client.login.mockResolvedValue({ token: 'tok-123' })
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/^password/i), 's3cret-pass')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(
      await screen.findByRole('heading', {
        name: /welcome back, alice/i,
      }),
    ).toBeInTheDocument()
    expect(client.login).toHaveBeenCalledWith('alice', 's3cret-pass')
  })

  it('shows a readable error when login fails', async () => {
    client.login.mockRejectedValue({
      response: {
        data: {
          non_field_errors: [
            'Unable to log in with provided credentials.',
          ],
        },
      },
    })
    const user = userEvent.setup()
    renderApp()

    await user.type(screen.getByLabelText(/username/i), 'alice')
    await user.type(screen.getByLabelText(/^password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(
      await screen.findByText(/unable to log in/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: /welcome back/i }),
    ).not.toBeInTheDocument()
  })

  it('rejects sign-up when the passwords do not match', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('tab', { name: 'Sign up' }))
    await user.type(screen.getByLabelText(/username/i), 'carol')
    await user.type(screen.getByLabelText(/^password/i), 'first-pass')
    await user.type(
      screen.getByLabelText(/confirm password/i),
      'second-pass',
    )
    await user.click(
      screen.getByRole('button', { name: 'Create account' }),
    )

    expect(
      await screen.findByText(/passwords do not match/i),
    ).toBeInTheDocument()
    expect(client.register).not.toHaveBeenCalled()
  })

  it('signs up and lands on the home screen', async () => {
    client.register.mockResolvedValue({ token: 'tok-456' })
    client.fetchMe.mockResolvedValue({ id: 2, username: 'carol' })
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('tab', { name: 'Sign up' }))
    await user.type(screen.getByLabelText(/username/i), 'carol')
    await user.type(screen.getByLabelText(/^password/i), 's3cret-pass')
    await user.type(
      screen.getByLabelText(/confirm password/i),
      's3cret-pass',
    )
    await user.click(
      screen.getByRole('button', { name: 'Create account' }),
    )

    expect(
      await screen.findByRole('heading', {
        name: /welcome back, carol/i,
      }),
    ).toBeInTheDocument()
    expect(client.register).toHaveBeenCalledWith('carol', 's3cret-pass')
  })

  it('restores the session from localStorage on reload', async () => {
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-789')
    renderApp()

    expect(
      await screen.findByRole('heading', {
        name: /welcome back, alice/i,
      }),
    ).toBeInTheDocument()
  })

  it('sends a rejected stored session back to the login page', async () => {
    client.fetchMe.mockRejectedValue({ response: { status: 401 } })
    localStorage.setItem(TOKEN_KEY, 'stale-token')
    renderApp()

    expect(
      await screen.findByRole('tab', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('logs out from the sidebar and returns to the landing page', async () => {
    client.fetchMe.mockResolvedValue({ id: 1, username: 'alice' })
    localStorage.setItem(TOKEN_KEY, 'tok-789')
    const user = userEvent.setup()
    renderApp()

    await screen.findByRole('heading', {
      name: /welcome back, alice/i,
    })

    await user.click(screen.getByRole('button', { name: /log out/i }))

    expect(
      await screen.findByRole('tab', { name: 'Log in' }),
    ).toBeInTheDocument()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})
