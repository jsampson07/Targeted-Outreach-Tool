import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProtectedRoute } from './ProtectedRoute'

const useAuthMock = vi.fn()

vi.mock('../context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

function renderWithRoute(initialPath = '/protected') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login screen</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <div>Secret content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    useAuthMock.mockReset()
  })

  afterEach(() => {
    cleanup()
  })

  it('redirects to /login when unauthenticated', () => {
    useAuthMock.mockReturnValue({ isAuthenticated: false })
    renderWithRoute()
    expect(screen.getByText('Login screen')).toBeInTheDocument()
    expect(screen.queryByText('Secret content')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    useAuthMock.mockReturnValue({ isAuthenticated: true })
    renderWithRoute()
    expect(screen.getByText('Secret content')).toBeInTheDocument()
    expect(screen.queryByText('Login screen')).not.toBeInTheDocument()
  })
})
