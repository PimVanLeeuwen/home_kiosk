import type { Severity } from './types'

const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#39;': "'" }
const LEVELS: Record<string, Severity> = { ERROR: 'error', WARNING: 'warning', OK: 'ok', INFO: 'info' }

/** Telegram HTML as the plain text ntfy gets: tags dropped, entities read, at most one blank line in a row (collector `ntfy.plain`). */
export function plainText(html: string): string {
  return html
    .replace(/<[^>]+>/g, '')
    .replace(/&(amp|lt|gt|quot|#x27|#39);/g, (e) => ENTITIES[e] ?? e)
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export interface PhoneBanner {
  severity: Severity | null
  title: string
  message: string
}

/**
 * What the phone shows for a message: the first line, without its level word, as
 * the title, and the rest as the text. A title alone goes as the text under the
 * category's name, as the collector sends it (`core.notify`).
 */
export function phoneBanner(html: string, category: string | null): PhoneBanner {
  const [first, ...rest] = plainText(html).split('\n')
  const level = /^(ERROR|WARNING|OK|INFO)\b(?: · )?/.exec(first ?? '')
  const title = (level ? first.slice(level[0].length) : (first ?? '')).trim()
  const message = rest.join('\n').trim()
  const severity = level ? LEVELS[level[1]] : null
  return message ? { severity, title, message } : { severity, title: category ?? title, message: title }
}

/** A message's HTML without its first line, the title the page already shows; '' when nothing follows it. */
export function bodyHtml(html: string): string {
  const cut = html.indexOf('\n')
  return cut === -1 ? '' : html.slice(cut + 1).trim()
}
