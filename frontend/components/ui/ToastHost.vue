<script setup lang="ts">
import { CircleCheck, CircleX, Info, X } from 'lucide-vue-next'

const { toasts, dismiss } = useToast()
const icons = { success: CircleCheck, error: CircleX, info: Info }
const tones = {
  success: 'text-emerald-400',
  error: 'text-rose-400',
  info: 'text-cyan-400',
}
</script>

<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2" aria-live="polite">
    <TransitionGroup
      enter-active-class="transition duration-200"
      enter-from-class="translate-y-2 opacity-0"
      leave-active-class="transition duration-150"
      leave-to-class="opacity-0"
    >
      <div v-for="t in toasts" :key="t.id" class="glass-card pointer-events-auto flex items-start gap-3 p-4">
        <component :is="icons[t.kind]" class="mt-0.5 h-5 w-5 shrink-0" :class="tones[t.kind]" />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-white">{{ t.title }}</p>
          <p v-if="t.message" class="mt-0.5 break-words text-xs text-slate-400">{{ t.message }}</p>
        </div>
        <button class="text-slate-500 hover:text-slate-200" aria-label="Dismiss" @click="dismiss(t.id)">
          <X class="h-4 w-4" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
