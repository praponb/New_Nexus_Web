<script setup lang="ts">
import { Check, X } from 'lucide-vue-next'
import type { ProjectStatus } from '~/types/api'

const props = defineProps<{
  status: ProjectStatus | null
  lastActivePhase?: string
  progress: number
  qaIterations?: number
  maxQa?: number
}>()

const failed = computed(() => props.status === 'FAILED')
const current = computed(() => {
  if (props.status === 'COMPLETED') return PIPELINE_STEPS.length
  const phase = failed.value ? props.lastActivePhase : props.status
  return Math.max(0, stepIndexFor(phase))
})

function stateOf(i: number): 'done' | 'active' | 'failed' | 'pending' {
  if (i < current.value) return 'done'
  if (i === current.value) return failed.value ? 'failed' : 'active'
  return 'pending'
}
</script>

<template>
  <div class="glass-card p-5">
    <ol class="grid grid-cols-5 gap-2">
      <li v-for="(step, i) in PIPELINE_STEPS" :key="step.key" class="relative flex flex-col items-center text-center">
        <div
          v-if="i > 0"
          class="absolute right-1/2 top-4 h-0.5 w-full -translate-y-1/2"
          :class="stateOf(i) === 'pending' ? 'bg-slate-800' : 'accent-gradient'"
        />
        <div
          class="relative z-10 grid h-8 w-8 place-items-center rounded-full border-2 text-xs font-semibold transition"
          :class="{
            'border-transparent accent-gradient text-white': stateOf(i) === 'done',
            'border-indigo-400 bg-slate-950 text-indigo-200 shadow-glow': stateOf(i) === 'active',
            'border-rose-500 bg-rose-500/20 text-rose-200': stateOf(i) === 'failed',
            'border-slate-700 bg-slate-900 text-slate-500': stateOf(i) === 'pending',
          }"
        >
          <span v-if="stateOf(i) === 'active'" class="absolute inset-0 animate-pulse-ring rounded-full border-2 border-indigo-400" />
          <Check v-if="stateOf(i) === 'done'" class="h-4 w-4" />
          <X v-else-if="stateOf(i) === 'failed'" class="h-4 w-4" />
          <span v-else>{{ i + 1 }}</span>
        </div>
        <p
          class="mt-2 text-xs font-medium"
          :class="stateOf(i) === 'pending' ? 'text-slate-500' : stateOf(i) === 'failed' ? 'text-rose-300' : 'text-slate-200'"
        >
          <span class="hidden sm:inline">{{ step.label }}</span>
          <span class="sm:hidden">{{ step.short }}</span>
        </p>
        <p v-if="step.key === 'qa' && qaIterations" class="mt-0.5 text-[11px] text-slate-500">
          loop {{ qaIterations }}/{{ maxQa || 3 }}
        </p>
      </li>
    </ol>
    <div class="mt-5 flex items-center gap-3">
      <div class="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
        <div
          class="h-full rounded-full transition-all duration-700"
          :class="failed ? 'bg-rose-500' : status === 'COMPLETED' ? 'bg-emerald-500' : 'shimmer-bar'"
          :style="{ width: `${Math.max(progress, 2)}%` }"
        />
      </div>
      <span class="w-10 text-right font-mono text-xs text-slate-400">{{ progress }}%</span>
    </div>
  </div>
</template>
