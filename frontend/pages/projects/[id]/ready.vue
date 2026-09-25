<script setup lang="ts">
import { ArrowLeft, Check, Clock, Copy, FileCode, Hash, PartyPopper, RefreshCw, ShieldCheck, Terminal } from 'lucide-vue-next'
import type { FileTree, ProjectDetail } from '~/types/api'

const route = useRoute()
const id = computed(() => String(route.params.id))
const projects = useProjects()
const toast = useToast()

const project = ref<ProjectDetail | null>(null)
const tree = ref<FileTree | null>(null)
const readme = ref('')
const loading = ref(true)
const downloading = ref(false)
const copied = ref(false)
const initialFile = computed(() => (typeof route.query.file === 'string' ? route.query.file : undefined))

useHead(() => ({ title: `Delivery · ${project.value?.name ?? 'Nexus'}` }))

const startCommand = computed(() => {
  const name = project.value?.artifact?.file_name ?? 'nexus_project.zip'
  return `unzip ${name} && cd ${project.value?.slug ?? 'project'}_generated && ./start_servers.sh`
})

const stats = computed(() => {
  const a = project.value?.artifact
  const t = project.value?.latest_task
  return [
    { icon: FileCode, label: 'Lines of code', value: formatNumber(a?.total_lines_of_code) },
    { icon: Hash, label: 'Files', value: formatNumber(a?.total_files_count) },
    { icon: ShieldCheck, label: 'QA loops', value: String(t?.qa_iterations ?? '—') },
    { icon: Clock, label: 'Generation time', value: formatDuration(t?.duration_seconds) },
  ]
})

onMounted(async () => {
  try {
    project.value = await projects.get(id.value)
    if (project.value.status !== 'COMPLETED') {
      await navigateTo(`/projects/${id.value}/mission-control`, { replace: true })
      return
    }
    tree.value = await projects.files(id.value)
    try {
      readme.value = (await projects.fileContent(id.value, 'README.md')).content ?? ''
    } catch {
      readme.value = ''
    }
  } catch (err: any) {
    toast.error('Could not load delivery', err?.message)
  } finally {
    loading.value = false
  }
})

async function download() {
  if (!project.value) return
  downloading.value = true
  try {
    const result = await projects.download(id.value, project.value.artifact?.file_name)
    toast.success('Download started', `${result.name} · ${formatBytes(result.size)}`)
  } catch (err: any) {
    toast.error('Download failed', err?.message)
  } finally {
    downloading.value = false
  }
}

async function copyCommand() {
  await navigator.clipboard.writeText(startCommand.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}
</script>

<template>
  <div class="space-y-6">
    <NuxtLink to="/dashboard" class="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
      <ArrowLeft class="h-4 w-4" /> All projects
    </NuxtLink>

    <div v-if="loading" class="glass-card h-72 animate-pulse" />

    <template v-else-if="project?.artifact">
      <section class="glass-card relative overflow-hidden p-8">
        <div class="accent-gradient absolute -left-24 -top-24 h-64 w-64 rounded-full opacity-20 blur-3xl" />
        <div class="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="flex items-center gap-3">
              <PartyPopper class="h-8 w-8 animate-bounce text-amber-300" />
              <h1 class="text-3xl font-bold tracking-tight text-white">{{ project.name }} is ready</h1>
            </div>
            <p class="mt-2 max-w-xl text-slate-400">
              Architected, coded, verified by QA and packaged. Inspect the code below or download the complete source.
            </p>
          </div>
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div v-for="s in stats" :key="s.label" class="rounded-xl border border-slate-800 bg-slate-950/50 px-4 py-3">
              <component :is="s.icon" class="h-4 w-4 text-indigo-300" />
              <p class="mt-2 text-xl font-semibold text-white">{{ s.value }}</p>
              <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ s.label }}</p>
            </div>
          </div>
        </div>
      </section>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div class="min-w-0 space-y-3">
          <h2 class="text-lg font-semibold text-white">Code explorer</h2>
          <CodeViewer :project-id="id" :tree="tree" :initial-path="initialFile" />
        </div>
        <aside class="space-y-6">
          <DownloadCard :artifact="project.artifact" :loading="downloading" @download="download" />
          <div class="glass-card p-5">
            <p class="flex items-center gap-2 text-sm font-medium text-slate-200"><Terminal class="h-4 w-4 text-cyan-300" /> Quick start</p>
            <div class="mt-3 flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3">
              <code class="flex-1 break-all font-mono text-xs text-cyan-200">{{ startCommand }}</code>
              <button class="text-slate-400 hover:text-white" aria-label="Copy command" @click="copyCommand">
                <component :is="copied ? Check : Copy" class="h-4 w-4" />
              </button>
            </div>
            <p class="mt-2 text-xs text-slate-500">Needs Python 3.10+ and Node 18+. Frontend on :3000, API on :8000, or the next free ports if those are busy (the script prints the URLs).</p>
          </div>
          <BaseButton :to="`/projects/${id}`" variant="secondary" block>
            <RefreshCw class="h-4 w-4" /> Refine requirement &amp; regenerate
          </BaseButton>
        </aside>
      </div>

      <section v-if="readme" class="glass-card p-8">
        <p class="label">README.md</p>
        <div class="prose prose-invert max-w-none prose-headings:text-slate-100 prose-a:text-indigo-300 prose-code:text-cyan-200" v-html="renderMarkdown(readme)" />
      </section>
    </template>

    <div v-else class="glass-card p-6 text-sm text-slate-400">This project has no packaged archive yet.</div>
  </div>
</template>
