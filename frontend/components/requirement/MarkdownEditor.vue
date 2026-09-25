<script setup lang="ts">
import { Columns2, Eye, PencilLine } from 'lucide-vue-next'

const model = defineModel<string>({ default: '' })
defineProps<{ disabled?: boolean }>()

const view = ref<'split' | 'write' | 'preview'>('split')
const html = computed(() => renderMarkdown(model.value))
const words = computed(() => countWords(model.value))
const pendingPreset = ref<string | null>(null)

function applyPreset(key: string) {
  const preset = REQUIREMENT_PRESETS.find((p) => p.key === key)
  if (!preset) return
  if (model.value.trim() && model.value !== preset.content && pendingPreset.value !== key) {
    pendingPreset.value = key // ask for a second click before overwriting work
    setTimeout(() => {
      if (pendingPreset.value === key) pendingPreset.value = null
    }, 3000)
    return
  }
  pendingPreset.value = null
  model.value = preset.content
}

function onTab(e: KeyboardEvent) {
  const el = e.target as HTMLTextAreaElement
  const { selectionStart: start, selectionEnd: end } = el
  model.value = model.value.slice(0, start) + '  ' + model.value.slice(end)
  nextTick(() => el.setSelectionRange(start + 2, start + 2))
}
</script>

<template>
  <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/40">
    <div class="flex flex-wrap items-center gap-2 border-b border-slate-800 px-3 py-2">
      <span class="mr-1 text-xs text-slate-500">Templates:</span>
      <button
        v-for="preset in REQUIREMENT_PRESETS"
        :key="preset.key"
        class="rounded-full border px-2.5 py-1 text-xs transition"
        :class="pendingPreset === preset.key
          ? 'border-amber-500/50 bg-amber-500/10 text-amber-200'
          : 'border-slate-700 text-slate-300 hover:border-indigo-500/60 hover:text-white'"
        :disabled="disabled"
        @click="applyPreset(preset.key)"
      >
        {{ pendingPreset === preset.key ? 'Click again to replace' : preset.label }}
      </button>
      <div class="ml-auto flex rounded-lg border border-slate-800 p-0.5">
        <button
          v-for="opt in [{ k: 'write', icon: PencilLine, label: 'Write' }, { k: 'split', icon: Columns2, label: 'Split' }, { k: 'preview', icon: Eye, label: 'Preview' }]"
          :key="opt.k"
          class="flex items-center gap-1 rounded-md px-2 py-1 text-xs transition"
          :class="view === opt.k ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'"
          @click="view = opt.k as typeof view"
        >
          <component :is="opt.icon" class="h-3.5 w-3.5" />
          {{ opt.label }}
        </button>
      </div>
    </div>
    <div class="grid h-[28rem]" :class="view === 'split' ? 'md:grid-cols-2' : 'grid-cols-1'">
      <textarea
        v-show="view !== 'preview'"
        v-model="model"
        :disabled="disabled"
        spellcheck="false"
        placeholder="# My App&#10;&#10;Describe the features, data and pages you need…"
        class="h-full w-full resize-none bg-transparent p-4 font-mono text-[13px] leading-relaxed text-slate-200 placeholder-slate-600 focus:outline-none"
        :class="view === 'split' && 'md:border-r md:border-slate-800'"
        data-testid="requirement-editor"
        @keydown.tab.prevent="onTab"
      />
      <div
        v-show="view !== 'write'"
        class="prose prose-sm prose-invert h-full max-w-none overflow-auto p-4 prose-headings:text-slate-100 prose-a:text-indigo-300"
        :class="view === 'split' && 'hidden md:block'"
      >
        <div v-if="model.trim()" v-html="html" />
        <p v-else class="text-slate-600">Preview appears here.</p>
      </div>
    </div>
    <div class="flex items-center justify-between border-t border-slate-800 px-4 py-2 text-xs text-slate-500">
      <span>{{ words }} words</span>
      <span :class="words < 20 ? 'text-amber-400' : 'text-emerald-400'">{{ words < 20 ? `${20 - words} more words needed` : 'Ready' }}</span>
    </div>
  </div>
</template>
