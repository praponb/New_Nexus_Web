<script setup lang="ts">
import { Check, Copy, FileCode, LoaderCircle } from 'lucide-vue-next'
import type { FileContent, FileTree } from '~/types/api'

const props = defineProps<{ projectId: string; tree: FileTree | null; initialPath?: string }>()

const { fileContent } = useProjects()
const selected = ref<string | null>(null)
const file = ref<FileContent | null>(null)
const html = ref('')
const loading = ref(false)
const error = ref('')
const copied = ref(false)
const cache = new Map<string, { file: FileContent; html: string }>()

function firstFile(): string | null {
  const preferred = [props.initialPath, 'README.md', 'frontend/pages/index.vue', 'backend/api/models.py']
  const all = new Set<string>()
  const walk = (n: any) => (n.type === 'file' ? all.add(n.path) : n.children?.forEach(walk))
  if (props.tree) walk(props.tree.root)
  return preferred.find((p) => p && all.has(p)) || [...all][0] || null
}

async function open(path: string) {
  selected.value = path
  error.value = ''
  const hit = cache.get(path)
  if (hit) {
    file.value = hit.file
    html.value = hit.html
    return
  }
  loading.value = true
  try {
    const data = await fileContent(props.projectId, path)
    const rendered = data.content != null ? await highlightCode(data.content, path) : ''
    cache.set(path, { file: data, html: rendered })
    if (selected.value === path) {
      file.value = data
      html.value = rendered
    }
  } catch (err: any) {
    error.value = err?.message || 'Could not load file.'
  } finally {
    loading.value = false
  }
}

async function copy() {
  if (!file.value?.content) return
  await navigator.clipboard.writeText(file.value.content)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

watch(
  () => props.tree,
  (tree) => {
    if (tree && !selected.value) {
      const path = firstFile()
      if (path) open(path)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="glass-card grid h-[36rem] min-h-0 overflow-hidden md:grid-cols-[16rem_minmax(0,1fr)]">
    <aside class="min-h-0 overflow-y-auto border-b border-slate-800 p-2 md:border-b-0 md:border-r" data-testid="code-tree">
      <p v-if="!tree" class="p-4 text-xs text-slate-500">Loading files…</p>
      <FileTreeNode
        v-for="child in tree?.root.children ?? []"
        :key="child.path"
        :node="child"
        :selected="selected"
        @select="open"
      />
    </aside>
    <section class="flex min-h-0 min-w-0 flex-col">
      <div class="flex items-center gap-2 border-b border-slate-800 px-4 py-2 text-xs">
        <FileCode class="h-3.5 w-3.5 text-slate-500" />
        <span class="truncate font-mono text-slate-300">{{ selected || 'Select a file' }}</span>
        <span v-if="file" class="text-slate-600">{{ formatBytes(file.size) }}</span>
        <LoaderCircle v-if="loading" class="h-3.5 w-3.5 animate-spin text-slate-500" />
        <button
          v-if="file?.content"
          class="ml-auto flex items-center gap-1 rounded-md px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          @click="copy"
        >
          <component :is="copied ? Check : Copy" class="h-3.5 w-3.5" /> {{ copied ? 'Copied' : 'Copy' }}
        </button>
      </div>
      <div class="shiki-host min-h-0 flex-1 overflow-auto bg-slate-950/60">
        <p v-if="error" class="p-4 text-sm text-rose-300">{{ error }}</p>
        <p v-else-if="file?.is_binary" class="p-4 text-sm text-slate-500">Binary file, preview not available.</p>
        <div v-else v-html="html" />
        <p v-if="file?.truncated" class="px-4 pb-4 text-xs text-amber-300">Preview truncated at 1 MB.</p>
      </div>
    </section>
  </div>
</template>
