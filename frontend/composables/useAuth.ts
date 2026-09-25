import { useAuthStore } from '~/stores/auth'
import type { Quota, Tokens, User } from '~/types/api'

export function useAuth() {
  const store = useAuthStore()
  const { request } = useApi()

  async function login(email: string, password: string) {
    const data = await request<{ user: User; tokens: Tokens }>('/api/v1/auth/login/', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
    store.setSession(data.user, data.tokens)
    return data.user
  }

  async function register(email: string, password: string, fullName = '') {
    const data = await request<{ user: User; tokens: Tokens }>('/api/v1/auth/register/', {
      method: 'POST',
      body: { email, password, full_name: fullName },
      auth: false,
    })
    store.setSession(data.user, data.tokens)
    return data.user
  }

  async function fetchMe() {
    const data = await request<{ user: User; quota: Quota }>('/api/v1/auth/me/')
    store.user = data.user
    store.quota = data.quota
    store.persist()
    return data
  }

  async function logout() {
    const refresh = store.tokens?.refresh
    try {
      if (refresh) await request('/api/v1/auth/logout/', { method: 'POST', body: { refresh } })
    } catch {
      /* the server-side blacklist is best effort */
    }
    store.clear()
    await navigateTo('/auth/login')
  }

  return {
    user: computed(() => store.user),
    quota: computed(() => store.quota),
    isAuthenticated: computed(() => store.isAuthenticated),
    login,
    register,
    fetchMe,
    logout,
  }
}
