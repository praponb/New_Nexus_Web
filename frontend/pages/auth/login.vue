<script setup lang="ts">
import { TriangleAlert } from 'lucide-vue-next'

definePageMeta({ layout: 'auth' })
useHead({ title: 'Sign in · Nexus' })

const { login } = useAuth()
const route = useRoute()
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (!email.value || !password.value) {
    error.value = 'Enter your email and password.'
    return
  }
  loading.value = true
  try {
    await login(email.value.trim(), password.value)
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/dashboard'
    await navigateTo(next)
  } catch (err: any) {
    error.value = err?.message || 'Sign in failed.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="glass-card p-8">
    <h2 class="text-2xl font-semibold text-white">Welcome back</h2>
    <p class="mt-1 text-sm text-slate-400">Sign in to continue building.</p>
    <div v-if="error" class="mt-5 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300" role="alert">
      <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
      {{ error }}
    </div>
    <form class="mt-6 space-y-4" novalidate @submit.prevent="submit">
      <BaseInput v-model="email" label="Email" type="email" autocomplete="email" placeholder="you@company.com" autofocus />
      <BaseInput v-model="password" label="Password" type="password" autocomplete="current-password" placeholder="••••••••" />
      <BaseButton type="submit" variant="glow" size="lg" block :loading="loading">Sign in</BaseButton>
    </form>
    <p class="mt-6 text-center text-sm text-slate-400">
      New to Nexus?
      <NuxtLink to="/auth/register" class="font-medium text-indigo-300 hover:text-indigo-200">Create an account</NuxtLink>
    </p>
  </div>
</template>
