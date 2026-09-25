import type { ProjectStatus } from '~/types/api'

export const ACTIVE_STATUSES: ProjectStatus[] = ['QUEUED', 'PLANNING', 'GENERATING', 'TESTING', 'PACKAGING']

export const PIPELINE_STEPS = [
  { key: 'analysis', label: 'Requirement Analysis', short: 'Analysis', statuses: ['QUEUED'] },
  { key: 'architecture', label: 'Architecture Design', short: 'Architecture', statuses: ['PLANNING'] },
  { key: 'coding', label: 'Parallel Coding', short: 'Coding', statuses: ['GENERATING'] },
  { key: 'qa', label: 'QA Self-Correction', short: 'QA', statuses: ['TESTING'] },
  { key: 'packaged', label: 'Packaged', short: 'Packaged', statuses: ['PACKAGING', 'COMPLETED'] },
] as const

export function stepIndexFor(status: string | null | undefined): number {
  if (!status) return -1
  return PIPELINE_STEPS.findIndex((s) => (s.statuses as readonly string[]).includes(status))
}

export const STATUS_META: Record<ProjectStatus, { label: string; tone: string; dot: string }> = {
  DRAFT: { label: 'Draft', tone: 'bg-slate-800 text-slate-300 ring-slate-700', dot: 'bg-slate-400' },
  QUEUED: { label: 'Queued', tone: 'bg-amber-500/10 text-amber-300 ring-amber-500/30', dot: 'bg-amber-400' },
  PLANNING: { label: 'Planning', tone: 'bg-indigo-500/10 text-indigo-300 ring-indigo-500/30', dot: 'bg-indigo-400' },
  GENERATING: { label: 'Building', tone: 'bg-indigo-500/10 text-indigo-300 ring-indigo-500/30', dot: 'bg-indigo-400' },
  TESTING: { label: 'Testing', tone: 'bg-cyan-500/10 text-cyan-300 ring-cyan-500/30', dot: 'bg-cyan-400' },
  PACKAGING: { label: 'Packaging', tone: 'bg-cyan-500/10 text-cyan-300 ring-cyan-500/30', dot: 'bg-cyan-400' },
  COMPLETED: { label: 'Ready for Download', tone: 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30', dot: 'bg-emerald-400' },
  FAILED: { label: 'Failed', tone: 'bg-rose-500/10 text-rose-300 ring-rose-500/30', dot: 'bg-rose-400' },
}

export const AGENTS = [
  { key: 'all', label: 'All' },
  { key: 'Team Lead', label: 'Team Lead' },
  { key: 'Frontend Dev', label: 'Frontend' },
  { key: 'Backend Dev', label: 'Backend' },
  { key: 'QA', label: 'QA Tester' },
] as const

export const AGENT_COLORS: Record<string, string> = {
  'Team Lead': 'text-indigo-300',
  'Frontend Dev': 'text-cyan-300',
  'Backend Dev': 'text-emerald-300',
  QA: 'text-amber-300',
  Packager: 'text-fuchsia-300',
  System: 'text-slate-400',
}

export function isActiveStatus(status: string | null | undefined): boolean {
  return Boolean(status && (ACTIVE_STATUSES as string[]).includes(status))
}
