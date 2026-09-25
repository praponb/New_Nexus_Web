import type { HighlighterGeneric } from 'shiki'

const LANGS = ['vue', 'typescript', 'javascript', 'json', 'python', 'markdown', 'css', 'html', 'shellscript', 'yaml', 'toml', 'ini']
const EXT_TO_LANG: Record<string, string> = {
  vue: 'vue',
  ts: 'typescript',
  mts: 'typescript',
  js: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  json: 'json',
  py: 'python',
  md: 'markdown',
  css: 'css',
  html: 'html',
  sh: 'shellscript',
  bash: 'shellscript',
  yml: 'yaml',
  yaml: 'yaml',
  toml: 'toml',
  cfg: 'ini',
  ini: 'ini',
  example: 'ini',
}

let highlighter: Promise<HighlighterGeneric<any, any>> | null = null

function getHighlighter() {
  if (!highlighter) {
    highlighter = import('shiki').then(({ createHighlighter }) =>
      createHighlighter({ themes: ['github-dark-default'], langs: LANGS }),
    )
  }
  return highlighter
}

export function langFor(path: string): string {
  const name = path.split('/').pop() || ''
  if (name === 'requirements.txt' || name === '.gitignore') return 'text'
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : ''
  return EXT_TO_LANG[ext] || 'text'
}

export async function highlightCode(code: string, path: string): Promise<string> {
  const lang = langFor(path)
  const hl = await getHighlighter()
  return hl.codeToHtml(code, { lang: lang === 'text' ? 'text' : lang, theme: 'github-dark-default' })
}
