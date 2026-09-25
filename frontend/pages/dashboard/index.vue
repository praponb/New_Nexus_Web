<script setup lang="ts">
import { Layers, Plus, RefreshCw, Sparkles } from 'lucide-vue-next'
import type { Project, ProjectDetail } from '~/types/api'

useHead({ title: 'Projects · Nexus' })

const { list, remove, download } = useProjects()
const { quota, fetchMe } = useAuth()
const toast = useToast()

const projects = ref<Project[]>([])
const loading = ref(true)
const loadError = ref('')
const showCreate = ref(false)
const toDelete = ref<Project | null>(null)
const deleting = ref(false)
const downloadingId = ref<string | null>(null)
let poll: ReturnType<typeof setInterval> | null = null

const hasActive = computed(() => projects.value.some((p) => isActiveStatus(p.status)))
const quotaPct = computed(() => {
  const q = quota.value
  return q ? Math.min(100, Math.round((q.generations_this_month / Math.max(q.monthly_generation_limit, 1)) * 100)) : 0
})

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    projects.value = await list()
    loadError.value = ''
  } catch (err: any) {
    loadError.value = err?.message || 'Could not load projects.'
  } finally {
    loading.value = false
  }
}

watch(hasActive, (active) => {
  if (active && !poll) poll = setInterval(() => load(true), 4000)
  if (!active && poll) {
    clearInterval(poll)
    poll = null
    fetchMe().catch(() => {})
  }
})

onMounted(() => {
  load()
  fetchMe().catch(() => {})
})
onBeforeUnmount(() => poll && clearInterval(poll))

function onCreated(project: ProjectDetail) {
  toast.success('Project created', project.name)
  navigateTo(`/projects/${project.id}`)
}

async function confirmDelete() {
  if (!toDelete.value) return
  deleting.value = true
  try {
    await remove(toDelete.value.id)
    projects.value = projects.value.filter((p) => p.id !== toDelete.value!.id)
    toast.success('Project deleted', toDelete.value.name)
    toDelete.value = null
    fetchMe().catch(() => {})
  } catch (err: any) {
    toast.error('Delete failed', err?.message)
  } finally {
    deleting.value = false
  }
}

async function onDownload(project: Project) {
  downloadingId.value = project.id
  try {
    const result = await download(project.id, `nexus_project_${project.slug}.zip`)
    toast.success('Download started', `${result.name} · ${formatBytes(result.size)}`)
  } catch (err: any) {
    toast.error('Download failed', err?.message)
  } finally {
    downloadingId.value = null
  }
}
</script>

<template>
  <div class="space-y-8">
    <section class="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="text-3xl font-bold tracking-tight text-white">Your projects</h1>
        <p class="mt-1 text-slate-400">Each project turns one requirement document into a downloadable full-stack app.</p>
      </div>
      <div class="flex flex-wrap items-center gap-4">
        <div v-if="quota" class="glass-card w-64 px-4 py-3">
          <div class="flex items-center justify-between text-xs">
            <span class="text-slate-400">Generations this month</span>
            <span class="font-mono text-slate-200">{{ quota.generations_this_month }} / {{ quota.monthly_generation_limit }}</span>
          </div>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div class="accent-gradient h-full rounded-full" :style="{ width: `${quotaPct}%` }" />
          </div>
        </div>
        <BaseButton variant="glow" size="lg" @click="showCreate = true">
          <Plus class="h-4 w-4" />
          New WebApp Project
        </BaseButton>
      </div>
    </section>

    <div v-if="loading" class="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      <div v-for="i in 3" :key="i" class="glass-card h-56 animate-pulse" />
    </div>

    <div v-else-if="loadError" class="glass-card flex items-center justify-between gap-4 p-6">
      <p class="text-sm text-rose-300">{{ loadError }}</p>
      <BaseButton variant="secondary" size="sm" @click="load()"><RefreshCw class="h-3.5 w-3.5" /> Retry</BaseButton>
    </div>

    <div v-else-if="!projects.length" class="glass-card flex flex-col items-center px-6 py-16 text-center">
      <div class="accent-gradient grid h-14 w-14 place-items-center rounded-2xl shadow-glow">
        <Sparkles class="h-7 w-7 text-white" />
      </div>
      <h2 class="mt-5 text-xl font-semibold text-white">Build your first app</h2>
      <p class="mt-2 max-w-md text-sm text-slate-400">
        Create a project, drop in a <span class="font-mono text-cyan-300">user_requirement.md</span>, and watch four agents
        design, code, test and package it.
      </p>
      <BaseButton class="mt-6" variant="glow" @click="showCreate = true"><Plus class="h-4 w-4" /> New WebApp Project</BaseButton>
    </div>

    <template v-else>
      <div class="flex items-center gap-2 text-sm text-slate-500">
        <Layers class="h-4 w-4" />
        {{ projects.length }} project{{ projects.length === 1 ? '' : 's' }}
        <span v-if="hasActive" class="text-indigo-300">· live updating</span>
      </div>
      <div class="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        <ProjectCard
          v-for="project in projects"
          :key="project.id"
          :project="project"
          :downloading="downloadingId === project.id"
          @delete="toDelete = $event"
          @download="onDownload"
        />
      </div>
    </template>

    <CreateProjectModal v-model:open="showCreate" @created="onCreated" />
    <ConfirmDialog
      :open="Boolean(toDelete)"
      title="Delete project?"
      :message="`“${toDelete?.name}” and all of its generated files will be permanently removed.`"
      :loading="deleting"
      @update:open="(v: boolean) => { if (!v) toDelete = null }"
      @confirm="confirmDelete"
    />
  </div>
</template>
