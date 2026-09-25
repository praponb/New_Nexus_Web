import type { FileNode } from '~/types/api'

export interface TreeEntry {
  path: string
  meta?: Record<string, unknown>
}

/** Build a sorted directory tree from flat relative paths. */
export function buildTree(entries: TreeEntry[]): FileNode {
  const root: FileNode = { name: '', path: '', type: 'directory', children: [] }
  const dirs = new Map<string, FileNode>([['', root]])
  for (const { path } of entries) {
    const parts = path.split('/').filter(Boolean)
    let parentPath = ''
    parts.forEach((part, i) => {
      const current = parts.slice(0, i + 1).join('/')
      const isFile = i === parts.length - 1
      if (isFile) {
        const parent = dirs.get(parentPath)!
        if (!parent.children!.some((c) => c.path === current)) {
          parent.children!.push({ name: part, path: current, type: 'file', extension: part.split('.').pop() || '' })
        }
      } else if (!dirs.has(current)) {
        const node: FileNode = { name: part, path: current, type: 'directory', children: [] }
        dirs.get(parentPath)!.children!.push(node)
        dirs.set(current, node)
      }
      parentPath = current
    })
  }
  const sort = (node: FileNode) => {
    node.children?.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'directory' ? -1 : 1))
    node.children?.forEach(sort)
  }
  sort(root)
  return root
}

export function countFiles(node: FileNode): number {
  if (node.type === 'file') return 1
  return (node.children ?? []).reduce((sum, child) => sum + countFiles(child), 0)
}

const EXT_COLORS: Record<string, string> = {
  vue: 'text-emerald-400',
  ts: 'text-sky-400',
  js: 'text-yellow-300',
  py: 'text-amber-300',
  json: 'text-orange-300',
  md: 'text-slate-300',
  css: 'text-pink-300',
  html: 'text-orange-400',
  sh: 'text-lime-300',
  txt: 'text-slate-400',
}

export function extColor(ext?: string): string {
  return EXT_COLORS[(ext || '').toLowerCase()] || 'text-slate-400'
}
