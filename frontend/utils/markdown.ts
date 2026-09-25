import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: false })

/** Render untrusted Markdown to sanitized HTML. */
export function renderMarkdown(source: string): string {
  const html = marked.parse(source || '', { async: false }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}
