import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from '../lib/apiClient'
import { AuthProvider, useAuth } from './AuthContext'

function AuthProbe() {
  const { isAuthenticated, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth-state">
        {isAuthenticated ? 'authenticated' : 'anonymous'}
      </span>
      <button type="button" onClick={() => void logout()}>
        Log out
      </button>
    </div>
  )
}

function seedTokens() {
  localStorage.setItem(ACCESS_TOKEN_KEY, 'access-token')
  localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh-token')
}

function renderAuth() {
  return render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  )
}

describe('AuthContext.logout', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    cleanup()
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('happy path: POSTs /auth/logout with refresh_token, clears storage, sets unauthenticated', async () => {
    const user = userEvent.setup()
    seedTokens()
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }))

    renderAuth()
    expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated')

    await user.click(screen.getByRole('button', { name: /log out/i }))

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous')
    })
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/logout',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ refresh_token: 'refresh-token' }),
      }),
    )
  })

  it('still clears client state when fetch rejects (network error)', async () => {
    const user = userEvent.setup()
    seedTokens()
    vi.mocked(fetch).mockRejectedValue(new TypeError('Failed to fetch'))

    renderAuth()
    expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated')

    await user.click(screen.getByRole('button', { name: /log out/i }))

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous')
    })
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
  })

  it('still clears client state when server returns non-2xx', async () => {
    const user = userEvent.setup()
    seedTokens()
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'Could not validate credentials.',
          error_code: 'AuthenticationError',
        }),
        { status: 401 },
      ),
    )

    renderAuth()
    expect(screen.getByTestId('auth-state')).toHaveTextContent('authenticated')

    await user.click(screen.getByRole('button', { name: /log out/i }))

    await waitFor(() => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent('anonymous')
    })
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
  })
})
