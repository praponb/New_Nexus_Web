import { defineStore } from 'pinia'
import type { Quota, Tokens, User } from '~/types/api'

const STORAGE_KEY = 'nexus.auth'

interface PersistedAuth {
  tokens: Tokens | null
  user: User | null
}

function readStorage(): PersistedAuth {
  if (!import.meta.client) return { tokens: null, user: null }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PersistedAuth) : { tokens: null, user: null }
  } catch {
    return { tokens: null, user: null }
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    ...readStorage(),
    quota: null as Quota | null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.tokens?.access),
    displayName: (state) => state.user?.full_name || state.user?.email?.split('@')[0] || '',
    initials(): string {
      const name = this.displayName || '?'
      return name
        .split(/[\s._-]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join('')
    },
  },
  actions: {
    persist() {
      if (!import.meta.client) return
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ tokens: this.tokens, user: this.user }))
      } catch {
        /* storage unavailable: session stays in memory */
      }
    },
    setSession(user: User, tokens: Tokens) {
      this.user = user
      this.tokens = tokens
      this.persist()
    },
    setAccess(access: string, refresh?: string) {
      if (!this.tokens) return
      this.tokens = { access, refresh: refresh || this.tokens.refresh }
      this.persist()
    },
    clear() {
      this.tokens = null
      this.user = null
      this.quota = null
      if (import.meta.client) localStorage.removeItem(STORAGE_KEY)
    },
  },
})
