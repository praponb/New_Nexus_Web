<script setup lang="ts">
import { TriangleAlert } from 'lucide-vue-next'
import { ApiError } from '~/composables/useApi'

definePageMeta({ layout: 'auth' })
useHead({ title: 'Create account · Nexus' })

const { register } = useAuth()
const fullName = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)
const error = ref('')
const fieldErrors = reactive<Record<string, string>>({})

function validate() {
  Object.keys(fieldErrors).forEach((k) => delete fieldErrors[k])
  if (!/^\S+@\S+\.\S+$/.test(email.value.trim())) fieldErrors.email = 'Enter a valid email address.'
  if (password.value.length < 8) fieldErrors.password = 'Use at least 8 characters.'
  if (confirm.value !== password.value) fieldErrors.confirm = 'Passwords do not match.'
  return Object.keys(fieldErrors).length === 0
}

async function submit() {
  error.value = ''
  if (!validate()) return
  loading.value = true
  try {
    await register(email.value.trim(), password.value, fullName.value.trim())
    await navigateTo('/dashboard')
  } catch (err: any) {
    const details = err instanceof ApiError ? (err.details as Record<string, string[]> | undefined) : undefined
    if (details && typeof details === 'object') {
      for (const [field, messages] of Object.entries(details)) {
        fieldErrors[field] = Array.isArray(messages) ? messages.join(' ') : String(messages)
      }
    }
    error.value = err?.message || 'Registration failed.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="glass-card p-8">
    <h2 class="text-2xl font-semibold text-white">Create your account</h2>
    <p class="mt-1 text-sm text-slate-400">Start turning requirements into running apps.</p>
    <div v-if="error" class="mt-5 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300" role="alert">
      <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
      {{ error }}
    </div>
    <form class="mt-6 space-y-4" novalidate @submit.prevent="submit">
      <BaseInput v-model="fullName" label="Full name" autocomplete="name" placeholder="Alex Taylor" />
      <BaseInput v-model="email" label="Email" type="email" autocomplete="email" placeholder="you@company.com" :error="fieldErrors.email" />
      <BaseInput v-model="password" label="Password" type="password" autocomplete="new-password" placeholder="At least 8 characters" :error="fieldErrors.password" />
      <BaseInput v-model="confirm" label="Confirm password" type="password" autocomplete="new-password" :error="fieldErrors.confirm" />
      <BaseButton type="submit" variant="glow" size="lg" block :loading="loading">Create account</BaseButton>
    </form>
    <p class="mt-6 text-center text-sm text-slate-400">
      Already have an account?
      <NuxtLink to="/auth/login" class="font-medium text-indigo-300 hover:text-indigo-200">Sign in</NuxtLink>
    </p>
  </div>
</template>
