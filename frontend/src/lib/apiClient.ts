const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY }

export class ApiError extends Error {
  status: number
  user_message: string
  error_code: string

  constructor(
    status: number,
    user_message: string,
    error_code: string,
  ) {
    super(user_message)
    this.name = 'ApiError'
    this.status = status
    this.user_message = user_message
    this.error_code = error_code
  }
}

export type RequestOptions = {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  /** Skip attaching Authorization even if a token is present. */
  skipAuth?: boolean
}

function getBaseUrl(): string {
  const base = import.meta.env.VITE_API_BASE_URL
  if (!base) {
    throw new Error('VITE_API_BASE_URL is not set')
  }
  return base.replace(/\/$/, '')
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

function handleUnauthorized(): void {
  clearTokens()
  window.location.assign('/login')
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null
  }
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function toApiError(status: number, data: unknown): ApiError {
  const errBody = data as { user_message?: string; error_code?: string } | null
  return new ApiError(
    status,
    errBody?.user_message ?? 'Something went wrong. Please try again.',
    errBody?.error_code ?? 'UnknownError',
  )
}

/**
 * Thin fetch wrapper: JSON body/headers, Bearer token from localStorage,
 * shared 401 → clear tokens + redirect to /login (no refresh attempt).
 *
 * 401 session-clear/redirect only runs when an Authorization header was
 * actually sent. Login/signup also return 401 for bad credentials; those
 * calls use skipAuth so the form can surface user_message without a reload.
 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, headers = {}, skipAuth = false } = options
  const url = `${getBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`

  const finalHeaders: Record<string, string> = {
    ...headers,
  }

  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
  }

  let sentAuthorization = false
  if (!skipAuth) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    if (token) {
      finalHeaders['Authorization'] = `Bearer ${token}`
      sentAuthorization = true
    }
  }

  const response = await fetch(url, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  const data = await parseBody(response)

  if (response.status === 401) {
    if (sentAuthorization) {
      handleUnauthorized()
    }
    throw toApiError(401, data)
  }

  if (!response.ok) {
    throw toApiError(response.status, data)
  }

  return data as T
}
