import type { ReactNode } from 'react'
import { createElement } from 'react'

/**
 * Render `**bold**` spans as emphasis so markdown never leaks into the UI as
 * literal asterisks. Built from React nodes rather than raw HTML, so model
 * output can't inject markup.
 */
export function renderEmphasis(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4
      ? createElement('strong', { key: i }, part.slice(2, -2))
      : part,
  )
}

/** Split an answer into paragraphs, dropping blank runs. */
export function paragraphs(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
}
