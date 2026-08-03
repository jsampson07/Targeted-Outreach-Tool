import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  request,
} from '../lib/apiClient'

type TokenPair = {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

type AuthContextValue = {
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readInitialAuth(): boolean {
  return Boolean(localStorage.getItem(ACCESS_TOKEN_KEY))
}

function storeTokens(pair: TokenPair): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, pair.access_token)
  localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token)
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(readInitialAuth)

  const login = useCallback(async (email: string, password: string) => {
    const pair = await request<TokenPair>('/auth/login', {
      method: 'POST',
      body: { email, password },
      skipAuth: true,
    })
    storeTokens(pair)
    setIsAuthenticated(true)
  }, [])

  const signup = useCallback(async (email: string, password: string) => {
    // Backend returns TokenPairOut immediately (201) — same shape as login.
    const pair = await request<TokenPair>('/auth/signup', {
      method: 'POST',
      body: { email, password },
      skipAuth: true,
    })
    storeTokens(pair)
    setIsAuthenticated(true)
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
    if (refreshToken) {
      try {
        // Real endpoint exists: POST /auth/logout with { refresh_token }.
        await request('/auth/logout', {
          method: 'POST',
          body: { refresh_token: refreshToken },
          skipAuth: true,
        })
      } catch {
        // Still clear locally even if revoke fails (network / already revoked).
      }
    }
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  const value = useMemo(
    () => ({ isAuthenticated, login, signup, logout }),
    [isAuthenticated, login, signup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
