<script setup lang="ts">
const model = defineModel<string>({ default: '' })

defineProps<{
  label?: string
  type?: string
  placeholder?: string
  error?: string
  hint?: string
  autocomplete?: string
  required?: boolean
  multiline?: boolean
  rows?: number
  autofocus?: boolean
}>()

const id = useId()
</script>

<template>
  <div>
    <label v-if="label" :for="id" class="label">{{ label }}</label>
    <textarea
      v-if="multiline"
      :id="id"
      v-model="model"
      :rows="rows || 3"
      :placeholder="placeholder"
      :required="required"
      class="w-full resize-none rounded-xl border bg-slate-950/60 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition focus:outline-none focus:ring-2"
      :class="error ? 'border-rose-500/60 focus:ring-rose-500/40' : 'border-slate-800 focus:border-indigo-500/70 focus:ring-indigo-500/30'"
    />
    <input
      v-else
      :id="id"
      v-model="model"
      :type="type || 'text'"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :required="required"
      :autofocus="autofocus"
      class="h-11 w-full rounded-xl border bg-slate-950/60 px-3.5 text-sm text-slate-100 placeholder-slate-500 transition focus:outline-none focus:ring-2"
      :class="error ? 'border-rose-500/60 focus:ring-rose-500/40' : 'border-slate-800 focus:border-indigo-500/70 focus:ring-indigo-500/30'"
    />
    <p v-if="error" class="mt-1.5 text-xs text-rose-400">{{ error }}</p>
    <p v-else-if="hint" class="mt-1.5 text-xs text-slate-500">{{ hint }}</p>
  </div>
</template>
