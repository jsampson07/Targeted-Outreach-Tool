import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext'
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from '../lib/apiClient'
import { LoginPage } from './LoginPage'

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Home stub</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('stores tokens and navigates home on successful submit', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'access-123',
          refresh_token: 'refresh-456',
          token_type: 'bearer',
        }),
        { status: 200 },
      ),
    )

    renderLogin()

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => {
      expect(screen.getByText('Home stub')).toBeInTheDocument()
    })
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('access-123')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('refresh-456')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/login',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('surfaces backend user_message on failed submit', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'Incorrect email or password',
          error_code: 'AuthenticationError',
        }),
        { status: 401 },
      ),
    )

    renderLogin()

    await user.type(screen.getByLabelText(/email/i), 'user@example.com')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /log in/i }))

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('Incorrect email or password')
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
  })
})
