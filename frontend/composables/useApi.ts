import { useAuthStore } from '~/stores/auth'

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, code = 'error', status = 0, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

type FetchOptions = Parameters<typeof $fetch>[1] & { auth?: boolean }

let refreshInFlight: Promise<boolean> | null = null

function toApiError(err: any): ApiError {
  if (err instanceof ApiError) return err
  const status = err?.response?.status ?? err?.statusCode ?? 0
  const body = err?.data ?? err?.response?._data
  const error = body?.error
  if (error?.message) return new ApiError(error.message, error.code || 'error', status, error.details)
  if (status === 0) return new ApiError('Cannot reach the Nexus API. Is the backend running?', 'network_error', 0)
  return new ApiError(err?.message || `Request failed (${status})`, 'error', status)
}

/** Refresh the access token once, sharing the request between concurrent callers. */
export async function refreshAccessToken(): Promise<boolean> {
  const auth = useAuthStore()
  if (!auth.tokens?.refresh) return false
  if (!refreshInFlight) {
    const { apiBase } = useRuntimeConfig().public
    refreshInFlight = $fetch<any>('/api/v1/auth/refresh/', {
      baseURL: apiBase,
      method: 'POST',
      body: { refresh: auth.tokens.refresh },
    })
      .then((res) => {
        auth.setAccess(res.data.access, res.data.refresh)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

export function useApi() {
  const { apiBase } = useRuntimeConfig().public

  async function raw<T = any>(path: string, options: FetchOptions = {}, retried = false): Promise<T> {
    const auth = useAuthStore()
    const { auth: withAuth = true, headers, ...rest } = options
    const merged = new Headers(headers as HeadersInit | undefined)
    if (withAuth && auth.tokens?.access) merged.set('Authorization', `Bearer ${auth.tokens.access}`)
    try {
      return (await $fetch<T>(path, { baseURL: apiBase, ...rest, headers: merged } as any)) as T
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 && withAuth && !retried && (await refreshAccessToken())) {
        return raw<T>(path, options, true)
      }
      if (status === 401 && withAuth) {
        auth.clear()
        if (import.meta.client && !useRoute().path.startsWith('/auth')) {
          await navigateTo({ path: '/auth/login', query: { next: useRoute().fullPath } })
        }
      }
      throw toApiError(err)
    }
  }

  /** Call the API and unwrap the `{ success, data }` envelope. */
  async function request<T = any>(path: string, options: FetchOptions = {}): Promise<T> {
    const res = await raw<{ success: boolean; data: T }>(path, options)
    return (res && typeof res === 'object' && 'data' in res ? res.data : res) as T
  }

  return { request, raw, apiBase }
}
