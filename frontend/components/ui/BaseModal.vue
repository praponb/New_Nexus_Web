<script setup lang="ts">
import { X } from 'lucide-vue-next'

const open = defineModel<boolean>('open', { default: false })
defineProps<{ title: string; description?: string; width?: string }>()

const panel = ref<HTMLElement | null>(null)

// `autofocus` does not fire for elements mounted after page load, so focus the first field on open.
watch(open, async (value) => {
  if (!value) return
  await nextTick()
  panel.value?.querySelector<HTMLElement>('input, textarea, select')?.focus()
})

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150"
      enter-from-class="opacity-0"
      leave-active-class="transition duration-100"
      leave-to-class="opacity-0"
    >
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" @click="open = false" />
        <div
          ref="panel"
          role="dialog"
          aria-modal="true"
          class="glass-card relative w-full animate-fade-up p-6"
          :class="width || 'max-w-lg'"
        >
          <button class="absolute right-4 top-4 text-slate-500 hover:text-slate-200" aria-label="Close" @click="open = false">
            <X class="h-5 w-5" />
          </button>
          <h2 class="text-lg font-semibold text-white">{{ title }}</h2>
          <p v-if="description" class="mt-1 text-sm text-slate-400">{{ description }}</p>
          <div class="mt-5">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
