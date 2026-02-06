import { env } from '../utils/env'

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public statusText: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('auth_token')
}

function buildUrl(path: string, params?: Record<string, string | number | boolean>): string {
  const url = new URL(path, env.API_BASE_URL)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.append(key, String(value))
    })
  }
  return url.toString()
}

async function handleResponse<T>(response: Response): Promise<T> {
  // Handle 401/403
  if (response.status === 401 || response.status === 403) {
    console.warn(`Authentication error: ${response.status} ${response.statusText}`)
    // TODO: Redirect to login or refresh token
  }

  // Parse response
  const contentType = response.headers.get('content-type')
  const isJson = contentType?.includes('application/json')

  if (!response.ok) {
    const errorBody = isJson ? await response.json() : await response.text()
    const errorMessage = typeof errorBody === 'object' && errorBody.detail
      ? errorBody.detail
      : typeof errorBody === 'string'
        ? errorBody
        : `Request failed: ${response.status} ${response.statusText}`

    throw new ApiError(errorMessage, response.status, response.statusText)
  }

  if (response.status === 204) {
    return null as T
  }

  return isJson ? response.json() : (response.text() as unknown as T)
}

export async function apiGet<T>(path: string, options?: RequestOptions): Promise<T> {
  const { params, ...fetchOptions } = options || {}
  const url = buildUrl(path, params)
  const token = getAuthToken()

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  })

  return handleResponse<T>(response)
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const { params, ...fetchOptions } = options || {}
  const url = buildUrl(path, params)
  const token = getAuthToken()

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...fetchOptions,
  })

  return handleResponse<T>(response)
}

export async function apiPatch<T>(
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const { params, ...fetchOptions } = options || {}
  const url = buildUrl(path, params)
  const token = getAuthToken()

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...fetchOptions,
  })

  return handleResponse<T>(response)
}

export async function apiPut<T>(
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const { params, ...fetchOptions } = options || {}
  const url = buildUrl(path, params)
  const token = getAuthToken()

  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...fetchOptions,
  })

  return handleResponse<T>(response)
}

export async function apiDelete<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const { params, ...fetchOptions } = options || {}
  const url = buildUrl(path, params)
  const token = getAuthToken()

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...fetchOptions.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...fetchOptions,
  })

  return handleResponse<T>(response)
}

export { ApiError }
