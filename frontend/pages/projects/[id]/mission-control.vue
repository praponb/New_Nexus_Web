<script setup lang="ts">
import { ArrowLeft, ArrowRight, Bot, RefreshCw, TriangleAlert, Wifi, WifiOff } from 'lucide-vue-next'
import type { ProjectDetail } from '~/types/api'

const route = useRoute()
const id = computed(() => String(route.params.id))
const projects = useProjects()
const toast = useToast()

const project = ref<ProjectDetail | null>(null)
const stream = useProjectSocket(id)
const restarting = ref(false)
const redirectIn = ref<number | null>(null)
let redirectTimer: ReturnType<typeof setInterval> | null = null

useHead(() => ({ title: `Mission Control · ${project.value?.name ?? 'Nexus'}` }))

const status = computed(() => stream.status.value ?? project.value?.status ?? null)
const live = computed(() => isActiveStatus(status.value))

onMounted(async () => {
  try {
    project.value = await projects.get(id.value)
  } catch (err: any) {
    toast.error('Could not load project', err?.message)
  }
  await stream.start()
})

watch(stream.completedAt, (at) => {
  if (!at) return
  toast.success('Your app is ready', 'QA passed and the archive is packaged.')
  redirectIn.value = 5
  redirectTimer = setInterval(() => {
    if (redirectIn.value === null) return
    redirectIn.value -= 1
    if (redirectIn.value <= 0) {
      clearInterval(redirectTimer!)
      navigateTo(`/projects/${id.value}/ready`)
    }
  }, 1000)
})

onBeforeUnmount(() => redirectTimer && clearInterval(redirectTimer))

function cancelRedirect() {
  if (redirectTimer) clearInterval(redirectTimer)
  redirectIn.value = null
}

async function restart() {
  restarting.value = true
  try {
    await projects.generate(id.value, true)
    stream.expectNewRun()
    toast.info('Generation restarted')
  } catch (err: any) {
    toast.error('Could not restart', err?.message)
  } finally {
    restarting.value = false
  }
}

function openFile(path: string) {
  if (status.value === 'COMPLETED') navigateTo({ path: `/projects/${id.value}/ready`, query: { file: path } })
}
</script>

<template>
  <div class="flex h-[calc(100vh-8rem)] min-h-[40rem] flex-col gap-4">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div class="min-w-0">
        <NuxtLink :to="`/projects/${id}`" class="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
          <ArrowLeft class="h-4 w-4" /> Requirement
        </NuxtLink>
        <div class="mt-1 flex items-center gap-3">
          <h1 class="truncate text-2xl font-bold tracking-tight text-white">{{ project?.name ?? 'Mission Control' }}</h1>
          <StatusBadge v-if="status" :status="status" size="md" />
        </div>
      </div>
      <div class="flex items-center gap-3">
        <span
          class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs"
          :class="stream.connected.value ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-300'"
          :title="stream.connectionError.value || 'Connected'"
        >
          <component :is="stream.connected.value ? Wifi : WifiOff" class="h-3.5 w-3.5" />
          {{ stream.connected.value ? 'Connected' : stream.connectionError.value || 'Connecting…' }}
        </span>
        <div v-if="stream.activeAgents.value.length" class="hidden items-center gap-1.5 text-xs text-slate-400 md:flex">
          <Bot class="h-3.5 w-3.5 text-cyan-300" /> {{ stream.activeAgents.value.join(' · ') }}
        </div>
        <BaseButton v-if="status === 'COMPLETED'" :to="`/projects/${id}/ready`" variant="glow">
          View delivery <ArrowRight class="h-4 w-4" />
        </BaseButton>
        <BaseButton v-else-if="status === 'FAILED'" variant="secondary" :loading="restarting" @click="restart">
          <RefreshCw class="h-4 w-4" /> Retry generation
        </BaseButton>
      </div>
    </header>

    <PipelineStepper
      :status="status"
      :last-active-phase="stream.lastActivePhase.value"
      :progress="stream.progress.value"
      :qa-iterations="stream.qaIterations.value"
    />

    <div v-if="status === 'FAILED'" class="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
      <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
      <div class="min-w-0">
        <p class="font-medium">Generation failed</p>
        <p class="mt-1 max-h-24 overflow-auto whitespace-pre-wrap text-rose-300/80">{{ stream.errorMessage.value || project?.error_message }}</p>
      </div>
    </div>
    <div v-else-if="redirectIn !== null" class="flex items-center justify-between rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
      <span>✅ All checks passed. Opening the delivery hub in {{ redirectIn }}s…</span>
      <button class="text-emerald-300 underline-offset-2 hover:underline" @click="cancelRedirect">Stay here</button>
    </div>

    <div class="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <TerminalStream
        :logs="stream.logs.value"
        :active-agents="stream.activeAgents.value"
        :last-file="stream.lastFile.value"
        :live="live"
      />
      <FileTreePreview :files="stream.files.value" :last-file="stream.lastFile.value" @select="openFile" />
    </div>
  </div>
</template>
