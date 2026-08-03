import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext'
import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from '../lib/apiClient'
import { SignupPage } from './SignupPage'

function renderSignup() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/signup']}>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/" element={<div>Home stub</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('SignupPage', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('stores tokens and navigates home on successful submit', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'access-signup',
          refresh_token: 'refresh-signup',
          token_type: 'bearer',
        }),
        { status: 201 },
      ),
    )

    renderSignup()

    await user.type(screen.getByLabelText(/email/i), 'new@example.com')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /sign up/i }))

    await waitFor(() => {
      expect(screen.getByText('Home stub')).toBeInTheDocument()
    })
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('access-signup')
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('refresh-signup')
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/auth/signup',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('surfaces backend user_message on failed submit', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'An account with this email already exists.',
          error_code: 'ConflictError',
        }),
        { status: 409 },
      ),
    )

    renderSignup()

    await user.type(screen.getByLabelText(/email/i), 'taken@example.com')
    await user.type(screen.getByLabelText(/password/i), 'secret')
    await user.click(screen.getByRole('button', { name: /sign up/i }))

    expect(
      await screen.findByRole('alert'),
    ).toHaveTextContent('An account with this email already exists.')
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
  })
})
