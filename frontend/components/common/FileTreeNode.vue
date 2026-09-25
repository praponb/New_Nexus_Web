<script setup lang="ts">
import { ChevronRight, FileCode, Folder, FolderOpen } from 'lucide-vue-next'
import type { FileNode } from '~/types/api'

const props = defineProps<{
  node: FileNode
  depth?: number
  selected?: string | null
  highlight?: string | null
  recent?: Set<string>
  expandAll?: boolean
}>()
const emit = defineEmits<{ select: [path: string] }>()

const depth = computed(() => props.depth ?? 0)
const open = ref(props.expandAll ?? depth.value < 2)
watch(
  () => props.highlight,
  (path) => {
    if (path && props.node.type === 'directory' && path.startsWith(props.node.path + '/')) open.value = true
  },
)
</script>

<template>
  <div>
    <button
      v-if="node.type === 'directory'"
      class="flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left text-[13px] text-slate-300 hover:bg-slate-800/60"
      :style="{ paddingLeft: `${depth * 12 + 6}px` }"
      @click="open = !open"
    >
      <ChevronRight class="h-3.5 w-3.5 shrink-0 text-slate-500 transition-transform" :class="open && 'rotate-90'" />
      <component :is="open ? FolderOpen : Folder" class="h-4 w-4 shrink-0 text-indigo-300/80" />
      <span class="truncate">{{ node.name }}</span>
    </button>
    <button
      v-else
      class="flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left text-[13px] transition"
      :class="[
        selected === node.path ? 'bg-indigo-500/15 text-white' : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200',
        highlight === node.path && 'animate-fade-up bg-cyan-500/10 text-cyan-200',
      ]"
      :style="{ paddingLeft: `${depth * 12 + 26}px` }"
      :title="node.path"
      @click="emit('select', node.path)"
    >
      <FileCode class="h-3.5 w-3.5 shrink-0" :class="extColor(node.extension)" />
      <span class="truncate">{{ node.name }}</span>
      <span v-if="recent?.has(node.path)" class="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
    </button>
    <div v-if="node.type === 'directory' && open">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :selected="selected"
        :highlight="highlight"
        :recent="recent"
        :expand-all="expandAll"
        @select="emit('select', $event)"
      />
    </div>
  </div>
</template>
