import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ACCESS_TOKEN_KEY,
  ApiError,
  REFRESH_TOKEN_KEY,
  request,
} from './apiClient'

describe('apiClient.request', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('attaches Authorization when access_token is in localStorage', async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, 'test-access')
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await request('/me')

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/me',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-access',
        }),
      }),
    )
  })

  it('omits Authorization when no access_token is present', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await request('/me')

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('on 401 with Authorization clears tokens and redirects to /login', async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_TOKEN_KEY, 'stale-refresh')
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })

    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'Could not validate credentials.',
          error_code: 'AuthenticationError',
        }),
        { status: 401 },
      ),
    )

    await expect(request('/me')).rejects.toBeInstanceOf(ApiError)

    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull()
    expect(assign).toHaveBeenCalledWith('/login')
  })

  it('on 401 without Authorization does not redirect (login failure)', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { assign })

    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'Incorrect email or password',
          error_code: 'AuthenticationError',
        }),
        { status: 401 },
      ),
    )

    await expect(
      request('/auth/login', {
        method: 'POST',
        body: { email: 'a@b.com', password: 'bad' },
        skipAuth: true,
      }),
    ).rejects.toMatchObject({
      user_message: 'Incorrect email or password',
    })

    expect(assign).not.toHaveBeenCalled()
  })

  it('throws ApiError with user_message and error_code on non-2xx', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          user_message: 'Email already registered.',
          error_code: 'ConflictError',
        }),
        { status: 409 },
      ),
    )

    try {
      await request('/auth/signup', {
        method: 'POST',
        body: { email: 'a@b.com', password: 'x' },
      })
      expect.fail('expected request to throw')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      const apiErr = err as ApiError
      expect(apiErr.status).toBe(409)
      expect(apiErr.user_message).toBe('Email already registered.')
      expect(apiErr.error_code).toBe('ConflictError')
    }
  })

  it('sends FormData without forcing JSON Content-Type', async () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, 'test-access')
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 201 }),
    )

    const body = new FormData()
    body.append('file', new File(['x'], 'resume.pdf', { type: 'application/pdf' }))
    await request('/resumes', { method: 'POST', body })

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit
    const headers = init.headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
    expect(init.body).toBeInstanceOf(FormData)
  })
})
