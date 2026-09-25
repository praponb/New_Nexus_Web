<script setup lang="ts">
import { ArrowDown, Brain, ChevronRight, CircleCheck, CircleX, Info, MessageSquare, Terminal, Wrench, Zap } from 'lucide-vue-next'
import type { AgentLog } from '~/types/api'

const props = defineProps<{ logs: AgentLog[]; activeAgents: string[]; lastFile?: { path: string; agent: string } | null; live?: boolean }>()

const filter = ref<string>('all')
const expanded = ref(new Set<number>())
const scroller = ref<HTMLElement | null>(null)
const pinned = ref(true)
const RENDER_LIMIT = 1500

const counts = computed(() => {
  const c: Record<string, number> = { all: props.logs.length }
  for (const log of props.logs) c[log.agent_name] = (c[log.agent_name] ?? 0) + 1
  return c
})
const filtered = computed(() => (filter.value === 'all' ? props.logs : props.logs.filter((l) => l.agent_name === filter.value)))
const visible = computed(() => filtered.value.slice(-RENDER_LIMIT))
const hidden = computed(() => filtered.value.length - visible.value.length)

const TYPE_META: Record<string, { icon: any; tone: string; label: string }> = {
  THOUGHT: { icon: Brain, tone: 'text-violet-300/80', label: 'Thought' },
  TOOL_CALL: { icon: Wrench, tone: 'text-cyan-300', label: 'Tool Call' },
  TOOL_RESULT: { icon: CircleCheck, tone: 'text-emerald-300/90', label: 'Result' },
  TEXT: { icon: MessageSquare, tone: 'text-slate-200', label: 'Message' },
  PHASE_CHANGE: { icon: Zap, tone: 'text-indigo-300', label: 'Phase' },
  SYSTEM: { icon: Info, tone: 'text-amber-200/90', label: 'Status' },
  ERROR: { icon: CircleX, tone: 'text-rose-300', label: 'Error' },
}

const isCollapsible = (log: AgentLog) =>
  (log.log_type === 'TOOL_RESULT' || log.log_type === 'ERROR' || log.log_type === 'TOOL_CALL') && (log.content.length > 180 || log.content.includes('\n') || Boolean(log.metadata?.args))

function toggle(seq: number) {
  const next = new Set(expanded.value)
  next.has(seq) ? next.delete(seq) : next.add(seq)
  expanded.value = next
}

function firstLine(text: string) {
  const line = text.split('\n')[0] ?? ''
  return line.length > 180 ? line.slice(0, 180) + '…' : line
}

function argsPreview(log: AgentLog) {
  const args = { ...(log.metadata?.args ?? {}) }
  return JSON.stringify(args, null, 2)
}

function onScroll() {
  const el = scroller.value
  if (!el) return
  pinned.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60
}

function scrollToBottom() {
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
  pinned.value = true
}

watch(
  () => [filtered.value.length, filter.value],
  () => nextTick(() => pinned.value && scrollToBottom()),
  { flush: 'post' },
)
</script>

<template>
  <div class="glass-card flex h-full min-h-0 flex-col overflow-hidden">
    <div class="flex flex-wrap items-center gap-1 border-b border-slate-800 px-3 py-2">
      <Terminal class="mr-1 h-4 w-4 text-slate-500" />
      <button
        v-for="agent in AGENTS"
        :key="agent.key"
        class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs transition"
        :class="filter === agent.key ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-slate-200'"
        @click="filter = agent.key"
      >
        <span
          v-if="agent.key !== 'all' && activeAgents.includes(agent.key)"
          class="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400"
        />
        {{ agent.label }}
        <span class="font-mono text-[10px] text-slate-500">{{ counts[agent.key] ?? 0 }}</span>
      </button>
      <span v-if="live" class="ml-auto flex items-center gap-1.5 text-[11px] text-emerald-400">
        <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> live
      </span>
    </div>

    <div
      ref="scroller"
      class="relative min-h-0 flex-1 overflow-y-auto bg-slate-950/60 px-3 py-2 font-mono text-[12.5px] leading-relaxed"
      data-testid="terminal-stream"
      @scroll="onScroll"
    >
      <p v-if="hidden > 0" class="py-1 text-center text-[11px] text-slate-600">… {{ hidden }} earlier events hidden</p>
      <p v-if="!visible.length" class="py-10 text-center text-slate-600">Waiting for agents to start…</p>
      <div v-for="log in visible" :key="log.sequence_num" class="group flex gap-2 py-0.5">
        <span class="w-16 shrink-0 select-none text-[11px] text-slate-600">{{ formatTime(log.timestamp) }}</span>
        <component :is="TYPE_META[log.log_type]?.icon ?? Info" class="mt-[3px] h-3.5 w-3.5 shrink-0" :class="TYPE_META[log.log_type]?.tone" />
        <span class="w-24 shrink-0 truncate text-[11px]" :class="AGENT_COLORS[log.agent_name] ?? 'text-slate-400'">{{ log.agent_name }}</span>
        <div class="min-w-0 flex-1" :class="TYPE_META[log.log_type]?.tone">
          <template v-if="isCollapsible(log)">
            <button class="flex max-w-full items-start gap-1 text-left hover:text-white" @click="toggle(log.sequence_num)">
              <ChevronRight class="mt-[3px] h-3 w-3 shrink-0 transition-transform" :class="expanded.has(log.sequence_num) && 'rotate-90'" />
              <span class="break-all">{{ firstLine(log.content) }}</span>
            </button>
            <pre
              v-if="expanded.has(log.sequence_num)"
              class="mt-1 max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-slate-800 bg-slate-900/80 p-2 text-[11.5px] text-slate-300"
            >{{ log.log_type === 'TOOL_CALL' && log.metadata?.args ? argsPreview(log) : log.content }}</pre>
          </template>
          <span v-else-if="log.log_type === 'THOUGHT'" class="whitespace-pre-wrap break-words italic">{{ log.content }}</span>
          <span v-else-if="log.log_type === 'PHASE_CHANGE'" class="font-semibold">{{ log.content }}</span>
          <span v-else class="whitespace-pre-wrap break-words">{{ log.content }}</span>
        </div>
      </div>
      <button
        v-if="!pinned"
        class="sticky bottom-2 left-full flex items-center gap-1 rounded-full bg-indigo-500 px-3 py-1 font-sans text-xs text-white shadow-glow"
        @click="scrollToBottom"
      >
        <ArrowDown class="h-3 w-3" /> Latest
      </button>
    </div>

    <div v-if="lastFile && live" class="flex items-center gap-2 border-t border-slate-800 bg-slate-900/60 px-3 py-2 text-xs">
      <Zap class="h-3.5 w-3.5 text-amber-300" />
      <span class="text-slate-500">{{ lastFile.agent || 'Agent' }} writing</span>
      <span class="truncate font-mono text-cyan-300">{{ lastFile.path }}</span>
    </div>
  </div>
</template>
