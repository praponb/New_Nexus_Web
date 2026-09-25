<script setup lang="ts">
import { FileText, TriangleAlert, Upload, X } from 'lucide-vue-next'

const MAX_BYTES = 5 * 1024 * 1024
const MIN_WORDS = 20

const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ select: [file: File, content: string] }>()

const dragging = ref(false)
const error = ref('')
const selected = ref<{ file: File; words: number } | null>(null)
const input = ref<HTMLInputElement | null>(null)

async function accept(file: File | undefined) {
  error.value = ''
  if (!file || props.disabled) return
  if (!file.name.toLowerCase().endsWith('.md')) {
    error.value = `“${file.name}” is not a Markdown (.md) file.`
    return
  }
  if (file.size > MAX_BYTES) {
    error.value = `File is ${formatBytes(file.size)}; the limit is 5 MB.`
    return
  }
  if (file.size === 0) {
    error.value = 'The file is empty.'
    return
  }
  const content = await file.text()
  const words = countWords(content)
  if (words < MIN_WORDS) {
    error.value = `The requirement needs at least ${MIN_WORDS} words (found ${words}).`
    return
  }
  selected.value = { file, words }
  emit('select', file, content)
}

function onDrop(e: DragEvent) {
  dragging.value = false
  accept(e.dataTransfer?.files?.[0])
}

function onPick(e: Event) {
  accept((e.target as HTMLInputElement).files?.[0])
  if (input.value) input.value.value = ''
}

function clear() {
  selected.value = null
  error.value = ''
}

defineExpose({ clear })
</script>

<template>
  <div>
    <div
      class="relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition"
      :class="[
        dragging ? 'border-indigo-400 bg-indigo-500/10' : 'border-slate-700 bg-slate-950/40 hover:border-slate-600',
        disabled && 'pointer-events-none opacity-50',
      ]"
      role="button"
      tabindex="0"
      aria-label="Upload user_requirement.md"
      @click="input?.click()"
      @keydown.enter.prevent="input?.click()"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <div class="grid h-14 w-14 place-items-center rounded-2xl border border-slate-700 bg-slate-900" :class="dragging && 'shadow-glow'">
        <Upload class="h-6 w-6 text-indigo-300" />
      </div>
      <p class="mt-4 text-sm font-medium text-slate-200">
        Drop <span class="font-mono text-cyan-300">user_requirement.md</span> here, or click to browse
      </p>
      <p class="mt-1 text-xs text-slate-500">Markdown only · up to 5 MB · at least {{ MIN_WORDS }} words</p>
      <input ref="input" type="file" accept=".md,text/markdown" class="hidden" data-testid="requirement-file" @change="onPick" />
    </div>

    <div v-if="error" class="mt-3 flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300" role="alert">
      <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" /> {{ error }}
    </div>
    <div v-else-if="selected" class="mt-3 flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
      <FileText class="h-4 w-4 text-emerald-300" />
      <span class="font-mono text-emerald-200">{{ selected.file.name }}</span>
      <span class="text-emerald-300/70">{{ formatBytes(selected.file.size) }} · {{ selected.words }} words</span>
      <button class="ml-auto text-emerald-300/70 hover:text-emerald-200" aria-label="Clear selection" @click="clear"><X class="h-4 w-4" /></button>
    </div>
  </div>
</template>
