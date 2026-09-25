import { useAuthStore } from '~/stores/auth'

const PUBLIC_PREFIXES = ['/auth']

export default defineNuxtRouteMiddleware((to) => {
  const auth = useAuthStore()
  const isPublic = PUBLIC_PREFIXES.some((prefix) => to.path.startsWith(prefix))

  if (!auth.isAuthenticated && !isPublic) {
    return navigateTo({ path: '/auth/login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} })
  }
  if (auth.isAuthenticated && isPublic) {
    return navigateTo('/dashboard')
  }
})
