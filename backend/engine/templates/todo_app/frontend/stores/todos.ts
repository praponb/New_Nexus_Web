import { defineStore } from 'pinia'

export interface Todo {
  id: number
  title: string
  description: string
  completed: boolean
  due_date: string | null
  created_at: string
  updated_at: string
}

export type TodoFilter = 'all' | 'active' | 'completed'

function api() {
  const base = useRuntimeConfig().public.apiBase
  return $fetch.create({ baseURL: `${base}/api` })
}

export const useTodoStore = defineStore('todos', {
  state: () => ({
    items: [] as Todo[],
    filter: 'all' as TodoFilter,
    loading: false,
    error: '',
  }),
  getters: {
    remaining: (state) => state.items.filter((t) => !t.completed).length,
  },
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const query = this.filter === 'all' ? {} : { status: this.filter }
        this.items = await api()<Todo[]>('/todos/', { query })
      } catch {
        this.error = `Could not reach the backend at ${useRuntimeConfig().public.apiBase}`
      } finally {
        this.loading = false
      }
    },
    async add(payload: { title: string; description?: string; due_date?: string | null }) {
      await api()('/todos/', { method: 'POST', body: payload })
      await this.load()
    },
    async toggle(todo: Todo) {
      await api()(`/todos/${todo.id}/`, { method: 'PATCH', body: { completed: !todo.completed } })
      await this.load()
    },
    async update(todo: Todo, patch: Partial<Todo>) {
      await api()(`/todos/${todo.id}/`, { method: 'PATCH', body: patch })
      await this.load()
    },
    async remove(todo: Todo) {
      await api()(`/todos/${todo.id}/`, { method: 'DELETE' })
      await this.load()
    },
  },
})
