<script setup lang="ts">
import { FolderTree } from 'lucide-vue-next'
import type { StreamedFile } from '~/composables/useProjectSocket'

const props = defineProps<{ files: StreamedFile[]; lastFile?: StreamedFile | null }>()
const emit = defineEmits<{ select: [path: string] }>()

const visibleFiles = computed(() => props.files.filter((f) => !f.path.startsWith('.agents/')))
const tree = computed(() => buildTree(visibleFiles.value))
const recent = computed(() => {
  const cutoff = Date.now() - 8000
  return new Set(visibleFiles.value.filter((f) => f.at > cutoff && f.agent).map((f) => f.path))
})
const notes = computed(() => props.files.filter((f) => f.path.startsWith('.agents/')).length)
</script>

<template>
  <div class="glass-card flex h-full min-h-0 flex-col overflow-hidden">
    <div class="flex items-center justify-between border-b border-slate-800 px-4 py-2.5">
      <div class="flex items-center gap-2 text-sm font-medium text-slate-200">
        <FolderTree class="h-4 w-4 text-indigo-300" /> Generated files
      </div>
      <span class="font-mono text-xs text-slate-500">{{ visibleFiles.length }}</span>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto p-2" data-testid="file-tree">
      <p v-if="!visibleFiles.length" class="px-2 py-8 text-center text-xs text-slate-600">Files appear here as agents write them.</p>
      <FileTreeNode
        v-for="child in tree.children"
        :key="child.path"
        :node="child"
        :highlight="lastFile?.path"
        :recent="recent"
        expand-all
        @select="emit('select', $event)"
      />
    </div>
    <p v-if="notes" class="border-t border-slate-800 px-4 py-2 text-[11px] text-slate-500">+ {{ notes }} agent planning notes</p>
  </div>
</template>
