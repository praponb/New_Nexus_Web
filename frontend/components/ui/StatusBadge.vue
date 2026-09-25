<script setup lang="ts">
import type { ProjectStatus } from '~/types/api'

const props = defineProps<{ status: ProjectStatus; size?: 'sm' | 'md' }>()
const meta = computed(() => STATUS_META[props.status] ?? STATUS_META.DRAFT)
const live = computed(() => isActiveStatus(props.status))
</script>

<template>
  <span
    class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full font-medium ring-1 ring-inset"
    :class="[meta.tone, size === 'md' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[11px]']"
  >
    <span class="relative flex h-1.5 w-1.5">
      <span v-if="live" class="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" :class="meta.dot" />
      <span class="relative inline-flex h-1.5 w-1.5 rounded-full" :class="meta.dot" />
    </span>
    {{ meta.label }}
  </span>
</template>
