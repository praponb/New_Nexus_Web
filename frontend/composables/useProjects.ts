import type { AgentLog, FileContent, FileTree, GenerationTask, Project, ProjectDetail, RequirementDoc } from '~/types/api'
import { useAuthStore } from '~/stores/auth'

export function useProjects() {
  const { request, raw, apiBase } = useApi()
  const base = '/api/v1/projects/'

  const list = () => request<Project[]>(base)
  const get = (id: string) => request<ProjectDetail>(`${base}${id}/`)
  const create = (payload: { name: string; description?: string }) =>
    request<ProjectDetail>(base, { method: 'POST', body: payload })
  const update = (id: string, payload: Partial<Pick<Project, 'name' | 'description'>>) =>
    request<Project>(`${base}${id}/`, { method: 'PATCH', body: payload })
  const remove = (id: string) => raw(`${base}${id}/`, { method: 'DELETE' })

  const getRequirement = (id: string) => request<RequirementDoc>(`${base}${id}/requirement/`)

  function uploadRequirementFile(id: string, file: File) {
    const form = new FormData()
    form.append('file', file)
    return request<RequirementDoc>(`${base}${id}/requirement/`, { method: 'POST', body: form })
  }

  const saveRequirementContent = (id: string, content: string) =>
    request<RequirementDoc>(`${base}${id}/requirement/`, { method: 'POST', body: { content } })

  const generate = (id: string, forceRestart = false) =>
    request<{ task_id: string; status: string }>(`${base}${id}/generate/`, {
      method: 'POST',
      body: { force_restart: forceRestart },
    })

  const logs = (id: string, after?: number) =>
    request<{ task: GenerationTask | null; logs: AgentLog[] }>(`${base}${id}/logs/`, {
      query: after ? { after } : undefined,
    })

  const files = (id: string) => request<FileTree>(`${base}${id}/files/`)
  const fileContent = (id: string, path: string) =>
    request<FileContent>(`${base}${id}/files/content/`, { query: { path } })

  /** Download the archive with the auth header, then hand the blob to the browser. */
  async function download(id: string, fallbackName = 'nexus_project.zip') {
    const auth = useAuthStore()
    const doFetch = () =>
      fetch(`${apiBase}${base}${id}/download/`, {
        headers: auth.tokens?.access ? { Authorization: `Bearer ${auth.tokens.access}` } : {},
      })
    let res = await doFetch()
    if (res.status === 401 && (await refreshAccessToken())) res = await doFetch()
    if (!res.ok) {
      let message = `Download failed (${res.status})`
      try {
        message = (await res.json())?.error?.message || message
      } catch {
        /* non-JSON body */
      }
      throw new ApiError(message, 'download_failed', res.status)
    }
    const disposition = res.headers.get('Content-Disposition') || ''
    const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] || fallbackName
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = name
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
    return { name, size: blob.size, checksum: res.headers.get('X-Checksum-SHA256') }
  }

  return {
    list,
    get,
    create,
    update,
    remove,
    getRequirement,
    uploadRequirementFile,
    saveRequirementContent,
    generate,
    logs,
    files,
    fileContent,
    download,
  }
}
