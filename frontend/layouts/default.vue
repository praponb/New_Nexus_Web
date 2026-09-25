<script setup lang="ts">
import { LogOut } from 'lucide-vue-next'
import { useAuthStore } from '~/stores/auth'

const store = useAuthStore()
const { logout, fetchMe } = useAuth()

onMounted(() => {
  if (store.isAuthenticated && !store.quota) fetchMe().catch(() => {})
})
</script>

<template>
  <div class="min-h-screen">
    <header class="sticky top-0 z-40 border-b border-slate-800/70 bg-slate-950/70 backdrop-blur-md">
      <div class="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <div class="flex items-center gap-8">
          <NexusLogo />
          <nav class="hidden items-center gap-1 text-sm sm:flex">
            <NuxtLink
              to="/dashboard"
              class="rounded-lg px-3 py-1.5 text-slate-400 transition hover:text-white"
              active-class="bg-slate-800/70 text-white"
            >
              Projects
            </NuxtLink>
          </nav>
        </div>
        <div class="flex items-center gap-3">
          <div v-if="store.user" class="hidden text-right sm:block">
            <p class="text-sm font-medium text-slate-200">{{ store.displayName }}</p>
            <p class="text-xs text-slate-500">{{ store.user.email }}</p>
          </div>
          <div
            class="accent-gradient grid h-9 w-9 place-items-center rounded-full text-xs font-bold text-white"
            :title="store.user?.email"
          >
            {{ store.initials }}
          </div>
          <button
            class="rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white"
            title="Sign out"
            aria-label="Sign out"
            @click="logout"
          >
            <LogOut class="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <slot />
    </main>
  </div>
</template>
