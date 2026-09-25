<script setup lang="ts">
import { Download, FileText, Rocket, Trash2 } from 'lucide-vue-next'
import type { Project } from '~/types/api'

const props = defineProps<{ project: Project; downloading?: boolean }>()
const emit = defineEmits<{ delete: [project: Project]; download: [project: Project] }>()

const active = computed(() => isActiveStatus(props.project.status))
const openTarget = computed(() => {
  const p = props.project
  if (p.status === 'COMPLETED') return `/projects/${p.id}/ready`
  if (active.value || p.status === 'FAILED') return `/projects/${p.id}/mission-control`
  return `/projects/${p.id}`
})
const openLabel = computed(() =>
  props.project.status === 'COMPLETED'
    ? 'View delivery'
    : active.value || props.project.status === 'FAILED'
      ? 'Open Mission Control'
      : 'Continue setup',
)
</script>

<template>
  <article class="glass-card group flex flex-col p-5 transition hover:border-slate-700 hover:shadow-glow">
    <div class="flex items-start justify-between gap-3">
      <NuxtLink :to="openTarget" class="min-w-0">
        <h3 class="truncate text-base font-semibold text-white group-hover:text-indigo-200">{{ project.name }}</h3>
        <p class="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-slate-400">
          {{ project.description || 'No description yet.' }}
        </p>
      </NuxtLink>
      <StatusBadge :status="project.status" />
    </div>

    <div v-if="active" class="mt-4">
      <div class="h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div class="shimmer-bar h-full rounded-full transition-all duration-500" :style="{ width: `${Math.max(project.progress_percentage, 4)}%` }" />
      </div>
      <p class="mt-1.5 text-xs text-slate-500">{{ project.progress_percentage }}% complete</p>
    </div>
    <p v-else-if="project.status === 'FAILED' && project.error_message" class="mt-4 line-clamp-2 text-xs text-rose-300/80">
      {{ project.error_message }}
    </p>

    <div class="mt-4 flex items-center gap-3 text-xs text-slate-500">
      <span class="inline-flex items-center gap-1">
        <FileText class="h-3.5 w-3.5" />
        {{ project.has_requirement ? 'Requirement ready' : 'No requirement' }}
      </span>
      <span>·</span>
      <span :title="project.created_at">Created {{ formatDate(project.created_at) }}</span>
    </div>

    <div class="mt-5 flex items-center gap-2 border-t border-slate-800/80 pt-4">
      <BaseButton :to="openTarget" size="sm" :variant="active ? 'primary' : 'secondary'">
        <Rocket class="h-3.5 w-3.5" />
        {{ openLabel }}
      </BaseButton>
      <BaseButton
        v-if="project.download_ready"
        size="sm"
        variant="secondary"
        :loading="downloading"
        title="Download zip"
        @click="emit('download', project)"
      >
        <Download class="h-3.5 w-3.5" />
        Zip
      </BaseButton>
      <button
        class="ml-auto rounded-lg p-2 text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-300"
        title="Delete project"
        :aria-label="`Delete ${project.name}`"
        @click="emit('delete', project)"
      >
        <Trash2 class="h-4 w-4" />
      </button>
    </div>
  </article>
</template>
