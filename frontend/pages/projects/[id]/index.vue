<script setup lang="ts">
import { ArrowLeft, FileText, PencilLine, Rocket, Save, TriangleAlert, Upload } from 'lucide-vue-next'
import type { ProjectDetail } from '~/types/api'

const route = useRoute()
const id = computed(() => String(route.params.id))
const projects = useProjects()
const toast = useToast()

const project = ref<ProjectDetail | null>(null)
const loading = ref(true)
const loadError = ref('')
const tab = ref<'upload' | 'editor'>('upload')
const content = ref('')
const savedContent = ref('')
const pendingFile = ref<File | null>(null)
const saving = ref(false)
const starting = ref(false)

useHead(() => ({ title: `${project.value?.name ?? 'Project'} · Nexus` }))

const active = computed(() => isActiveStatus(project.value?.status))
const words = computed(() => countWords(content.value))
const dirty = computed(() => Boolean(pendingFile.value) || content.value !== savedContent.value)
const canStart = computed(() => words.value >= 20 && !active.value)

async function load() {
  loading.value = true
  try {
    project.value = await projects.get(id.value)
    const doc = project.value.requirement
    content.value = doc?.raw_content ?? ''
    savedContent.value = content.value
    if (doc) tab.value = 'editor'
    loadError.value = ''
  } catch (err: any) {
    loadError.value = err?.message || 'Could not load the project.'
  } finally {
    loading.value = false
  }
}
onMounted(load)

function onFileSelected(file: File, text: string) {
  pendingFile.value = file
  content.value = text
}

async function save(silent = false) {
  saving.value = true
  try {
    const doc = pendingFile.value
      ? await projects.uploadRequirementFile(id.value, pendingFile.value)
      : await projects.saveRequirementContent(id.value, content.value)
    content.value = doc.raw_content
    savedContent.value = doc.raw_content
    pendingFile.value = null
    if (project.value) project.value.has_requirement = true
    if (!silent) toast.success('Draft saved', `${doc.original_filename} · ${doc.word_count} words`)
    return true
  } catch (err: any) {
    toast.error('Could not save requirement', err?.message)
    return false
  } finally {
    saving.value = false
  }
}

async function start() {
  starting.value = true
  try {
    if ((dirty.value || !project.value?.has_requirement) && !(await save(true))) return
    await projects.generate(id.value)
    toast.success('Generation started', 'Opening Mission Control…')
    await navigateTo(`/projects/${id.value}/mission-control`)
  } catch (err: any) {
    toast.error('Could not start generation', err?.message)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <NuxtLink to="/dashboard" class="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white">
      <ArrowLeft class="h-4 w-4" /> All projects
    </NuxtLink>

    <div v-if="loading" class="glass-card h-96 animate-pulse" />
    <div v-else-if="loadError" class="glass-card p-6 text-sm text-rose-300">{{ loadError }}</div>

    <template v-else-if="project">
      <header class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-3xl font-bold tracking-tight text-white">{{ project.name }}</h1>
            <StatusBadge :status="project.status" size="md" />
          </div>
          <p class="mt-1 text-slate-400">{{ project.description || 'Describe the app you want in a requirement document.' }}</p>
        </div>
        <BaseButton v-if="active" :to="`/projects/${project.id}/mission-control`" variant="primary">
          <Rocket class="h-4 w-4" /> Open Mission Control
        </BaseButton>
        <BaseButton v-else-if="project.status === 'COMPLETED'" :to="`/projects/${project.id}/ready`" variant="secondary">
          View delivery
        </BaseButton>
      </header>

      <div v-if="project.status === 'FAILED' && project.error_message" class="flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
        <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p class="font-medium">The last generation failed.</p>
          <p class="mt-1 whitespace-pre-wrap text-rose-300/80">{{ project.error_message.slice(0, 600) }}</p>
          <p class="mt-2 text-rose-300/80">Refine the requirement below and start again.</p>
        </div>
      </div>

      <section class="glass-card p-6">
        <div class="mb-5 flex items-center justify-between gap-4">
          <div class="flex rounded-xl border border-slate-800 bg-slate-950/50 p-1">
            <button
              class="flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition"
              :class="tab === 'upload' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'"
              @click="tab = 'upload'"
            >
              <Upload class="h-4 w-4" /> Upload
            </button>
            <button
              class="flex items-center gap-2 rounded-lg px-4 py-2 text-sm transition"
              :class="tab === 'editor' ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'"
              @click="tab = 'editor'"
            >
              <PencilLine class="h-4 w-4" /> Editor
            </button>
          </div>
          <p v-if="project.requirement" class="hidden items-center gap-1.5 text-xs text-slate-500 sm:flex">
            <FileText class="h-3.5 w-3.5" />
            Saved: {{ project.requirement.original_filename }} · {{ project.requirement.word_count }} words · {{ timeAgo(project.requirement.updated_at) }}
          </p>
        </div>

        <div v-show="tab === 'upload'">
          <FileUploadZone :disabled="active" @select="onFileSelected" />
          <div v-if="content.trim()" class="mt-5">
            <p class="label">Preview</p>
            <div class="prose prose-sm prose-invert max-h-80 max-w-none overflow-auto rounded-xl border border-slate-800 bg-slate-950/40 p-4" v-html="renderMarkdown(content)" />
          </div>
        </div>
        <div v-show="tab === 'editor'">
          <MarkdownEditor v-model="content" :disabled="active" />
        </div>
      </section>

      <div class="glass-card sticky bottom-4 flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-sm text-slate-400">
          <template v-if="active">Generation is running. The requirement is locked.</template>
          <template v-else-if="dirty">You have unsaved changes · {{ words }} words.</template>
          <template v-else-if="project.has_requirement">Requirement saved · {{ words }} words.</template>
          <template v-else>Upload a file or write your requirement to begin.</template>
        </p>
        <div class="flex gap-2">
          <BaseButton variant="secondary" :loading="saving" :disabled="!dirty || words < 20 || active" @click="save()">
            <Save class="h-4 w-4" /> Save Draft
          </BaseButton>
          <BaseButton variant="glow" size="lg" :loading="starting" :disabled="!canStart" data-testid="start-generation" @click="start">
            <Rocket class="h-4 w-4" /> Start Autonomous Generation
          </BaseButton>
        </div>
      </div>
    </template>
  </div>
</template>
