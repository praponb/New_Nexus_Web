<script setup lang="ts">
import { Download, FileArchive, Hash } from 'lucide-vue-next'
import type { Artifact } from '~/types/api'

const props = defineProps<{ artifact: Artifact; loading?: boolean }>()
const emit = defineEmits<{ download: [] }>()
</script>

<template>
  <div class="glass-card relative overflow-hidden p-6">
    <div class="accent-gradient absolute -right-16 -top-16 h-40 w-40 rounded-full opacity-20 blur-3xl" />
    <div class="flex items-start gap-4">
      <div class="accent-gradient grid h-12 w-12 shrink-0 place-items-center rounded-xl shadow-glow">
        <FileArchive class="h-6 w-6 text-white" />
      </div>
      <div class="min-w-0">
        <p class="truncate font-mono text-sm text-white">{{ artifact.file_name }}</p>
        <p class="mt-0.5 text-xs text-slate-400">
          {{ formatBytes(artifact.file_size_bytes) }} · {{ formatNumber(artifact.total_files_count) }} files ·
          {{ artifact.frontend_framework || 'Nuxt 3' }} + {{ artifact.backend_framework || 'Django 5' }}
        </p>
      </div>
    </div>
    <BaseButton class="mt-5 whitespace-nowrap" variant="glow" size="md" block :loading="props.loading" data-testid="download-zip" @click="emit('download')">
      <Download class="h-5 w-5" />
      Download Complete Source Code (.ZIP)
    </BaseButton>
    <p class="mt-3 flex items-center gap-1.5 break-all font-mono text-[11px] text-slate-500" :title="artifact.sha256_checksum">
      <Hash class="h-3 w-3 shrink-0" /> sha256 {{ artifact.sha256_checksum }}
    </p>
  </div>
</template>
