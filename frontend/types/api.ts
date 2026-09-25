export type ProjectStatus =
  | 'DRAFT'
  | 'QUEUED'
  | 'PLANNING'
  | 'GENERATING'
  | 'TESTING'
  | 'PACKAGING'
  | 'COMPLETED'
  | 'FAILED'

export type LogType = 'THOUGHT' | 'TOOL_CALL' | 'TOOL_RESULT' | 'TEXT' | 'PHASE_CHANGE' | 'SYSTEM' | 'ERROR'

export interface User {
  id: string
  email: string
  full_name: string
  created_at: string
}

export interface Tokens {
  access: string
  refresh: string
}

export interface Quota {
  projects_count: number
  completed_projects: number
  generations_this_month: number
  monthly_generation_limit: number
  remaining_generations: number
}

export interface RequirementPreview {
  id: string
  original_filename: string
  word_count: number
  preview: string
  truncated: boolean
  raw_content: string
  updated_at: string
}

export interface RequirementDoc {
  id: string
  original_filename: string
  raw_content: string
  word_count: number
  uploaded_at: string
  updated_at: string
}

export interface GenerationTask {
  id: string
  current_phase: string
  progress_percentage: number
  qa_iterations: number
  started_at: string | null
  finished_at: string | null
  created_at: string
  duration_seconds: number | null
}

export interface Artifact {
  id: string
  file_name: string
  file_size_bytes: number
  sha256_checksum: string
  total_files_count: number
  total_lines_of_code: number
  frontend_framework?: string
  backend_framework?: string
  created_at?: string
}

export interface Project {
  id: string
  name: string
  slug: string
  description: string
  status: ProjectStatus
  error_message: string | null
  has_requirement: boolean
  download_ready: boolean
  progress_percentage: number
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends Project {
  requirement: RequirementPreview | null
  latest_task: GenerationTask | null
  artifact: Artifact | null
}

export interface AgentLog {
  id?: number
  task_id: string
  agent_name: string
  log_type: LogType
  content: string
  metadata: Record<string, any>
  sequence_num: number
  timestamp: string
}

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  extension?: string
  children?: FileNode[]
}

export interface FileTree {
  root: FileNode
  total_files: number
  total_bytes: number
}

export interface FileContent {
  path: string
  size: number
  extension: string
  is_binary: boolean
  truncated: boolean
  content: string | null
}

export interface PhaseUpdate {
  task_id: string | null
  status: ProjectStatus
  current_phase: string
  progress_percentage: number
  qa_iterations: number
  active_agents: string[]
  files_created_count: number | null
  error_message?: string | null
  artifact?: Artifact | null
  snapshot?: boolean
}

export interface FileCreatedEvent {
  task_id: string
  agent_name: string
  path: string
  tool: string
  is_new: boolean
  files_created_count: number
}
