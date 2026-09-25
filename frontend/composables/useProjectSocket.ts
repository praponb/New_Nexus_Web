import type { AgentLog, Artifact, FileCreatedEvent, FileNode, PhaseUpdate, ProjectStatus } from '~/types/api'
import { useAuthStore } from '~/stores/auth'

export interface StreamedFile {
  path: string
  agent: string
  at: number
}

const MAX_BACKOFF_MS = 15_000

/**
 * Live connection to /ws/projects/{id}/logs/. Reconnects with backoff, resumes from the last
 * sequence number, and dedupes by sequence_num so replays never double-render.
 */
export function useProjectSocket(projectId: MaybeRefOrGetter<string>) {
  const { wsBase } = useRuntimeConfig().public
  const auth = useAuthStore()
  const projects = useProjects()

  const logs = ref<AgentLog[]>([])
  const status = ref<ProjectStatus | null>(null)
  const phase = ref<string>('')
  const lastActivePhase = ref<string>('')
  const progress = ref(0)
  const qaIterations = ref(0)
  const activeAgents = ref<string[]>([])
  const files = ref<StreamedFile[]>([])
  const lastFile = ref<StreamedFile | null>(null)
  const artifact = ref<Artifact | null>(null)
  const errorMessage = ref<string | null>(null)
  const connected = ref(false)
  const connectionError = ref<string | null>(null)
  const taskId = ref<string | null>(null)
  const completedAt = ref<number | null>(null)

  const seen = new Set<number>()
  const filePaths = new Map<string, StreamedFile>()
  let lastSeq = 0
  let socket: WebSocket | null = null
  let attempts = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let pingTimer: ReturnType<typeof setInterval> | null = null
  let closedByUser = false

  function reset(keepFiles = false) {
    logs.value = []
    seen.clear()
    if (!keepFiles) {
      filePaths.clear()
      files.value = []
    }
    lastSeq = 0
    lastFile.value = null
  }

  function addLogs(batch: AgentLog[]) {
    const fresh = batch.filter((log) => !seen.has(log.sequence_num))
    if (!fresh.length) return
    for (const log of fresh) {
      seen.add(log.sequence_num)
      lastSeq = Math.max(lastSeq, log.sequence_num)
      if (log.log_type === 'PHASE_CHANGE' && log.metadata?.phase) lastActivePhase.value = log.metadata.phase
    }
    const merged = logs.value.concat(fresh)
    const outOfOrder = merged.some((log, i) => i > 0 && log.sequence_num < merged[i - 1]!.sequence_num)
    if (outOfOrder) merged.sort((a, b) => a.sequence_num - b.sequence_num)
    logs.value = merged
  }

  function addFile(path: string, agent: string) {
    const existing = filePaths.get(path)
    const entry = { path, agent, at: Date.now() }
    filePaths.set(path, entry)
    if (!existing) files.value = [...files.value, entry]
    lastFile.value = entry
  }

  function flatten(node: FileNode, out: string[] = []): string[] {
    if (node.type === 'file') out.push(node.path)
    node.children?.forEach((child) => flatten(child, out))
    return out
  }

  async function seedFiles() {
    try {
      const tree = await projects.files(toValue(projectId))
      for (const path of flatten(tree.root)) if (!filePaths.has(path)) addFile(path, '')
      lastFile.value = null
    } catch {
      /* the file tree is a nicety; the stream still works */
    }
  }

  function applyPhase(data: PhaseUpdate) {
    if (data.task_id && taskId.value && data.task_id !== taskId.value) {
      // A new generation run started while we were connected.
      reset()
    }
    if (data.task_id) taskId.value = data.task_id
    status.value = data.status
    phase.value = data.current_phase
    if (data.current_phase && data.current_phase !== 'FAILED') lastActivePhase.value = data.current_phase
    progress.value = data.progress_percentage ?? progress.value
    qaIterations.value = data.qa_iterations ?? qaIterations.value
    activeAgents.value = data.active_agents ?? []
    if (data.snapshot) {
      errorMessage.value = data.error_message ?? null
      artifact.value = data.artifact ?? null
    }
  }

  function handle(event: { type: string; data: any }) {
    switch (event.type) {
      case 'history':
        if (event.data.task_id && taskId.value && event.data.task_id !== taskId.value) reset()
        taskId.value = event.data.task_id
        addLogs(event.data.logs)
        break
      case 'log_event':
        addLogs([event.data as AgentLog])
        break
      case 'phase_update':
        applyPhase(event.data as PhaseUpdate)
        break
      case 'file_created': {
        const data = event.data as FileCreatedEvent
        addFile(data.path, data.agent_name)
        break
      }
      case 'pipeline_complete':
        status.value = 'COMPLETED'
        progress.value = 100
        activeAgents.value = []
        artifact.value = event.data.artifact
        completedAt.value = Date.now()
        break
      case 'pipeline_failed':
        status.value = 'FAILED'
        activeAgents.value = []
        errorMessage.value = event.data.error_message
        break
    }
  }

  function scheduleReconnect() {
    if (closedByUser) return
    const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempts)
    attempts++
    retryTimer = setTimeout(connect, delay)
  }

  function connect() {
    if (!import.meta.client || closedByUser) return
    const token = auth.tokens?.access
    if (!token) {
      connectionError.value = 'Not signed in.'
      return
    }
    const url = `${wsBase}/ws/projects/${toValue(projectId)}/logs/?token=${encodeURIComponent(token)}${lastSeq ? `&after=${lastSeq}` : ''}`
    const ws = new WebSocket(url)
    socket = ws

    ws.onopen = () => {
      connected.value = true
      connectionError.value = null
      attempts = 0
      pingTimer = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send('{"type":"ping"}'), 25_000)
    }
    ws.onmessage = (msg) => {
      try {
        handle(JSON.parse(msg.data))
      } catch {
        /* ignore malformed frames */
      }
    }
    ws.onclose = async (evt) => {
      connected.value = false
      if (pingTimer) clearInterval(pingTimer)
      if (socket !== ws || closedByUser) return
      if (evt.code === 4401) {
        if (await refreshAccessToken()) return connect()
        connectionError.value = 'Session expired. Please sign in again.'
        return
      }
      if (evt.code === 4404) {
        connectionError.value = 'Project not found.'
        return
      }
      connectionError.value = 'Connection lost. Reconnecting…'
      scheduleReconnect()
    }
  }

  async function start() {
    closedByUser = false
    await seedFiles()
    connect()
  }

  function stop() {
    closedByUser = true
    if (retryTimer) clearTimeout(retryTimer)
    if (pingTimer) clearInterval(pingTimer)
    socket?.close(1000)
    socket = null
  }

  /** Call after POST /generate so the next run starts from a clean slate. A resumed run keeps
   *  the generated files, so pass `keepFiles` to leave the file tree in place. */
  function expectNewRun(keepFiles = false) {
    reset(keepFiles)
    status.value = 'QUEUED'
    progress.value = 0
    errorMessage.value = null
    artifact.value = null
    qaIterations.value = 0
    lastActivePhase.value = 'QUEUED'
    taskId.value = null
    stop()
    closedByUser = false
    connect()
  }

  onBeforeUnmount(stop)

  return {
    logs,
    status,
    phase,
    lastActivePhase,
    progress,
    qaIterations,
    activeAgents,
    files,
    lastFile,
    artifact,
    errorMessage,
    connected,
    connectionError,
    taskId,
    completedAt,
    start,
    stop,
    expectNewRun,
  }
}
