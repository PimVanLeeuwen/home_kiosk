/** Ask (plan.md M35): the chat with the house. The conversation lives in the page only. */

export interface AskMessage {
  role: 'user' | 'assistant'
  text: string
}

/** A change Claude asks for; nothing happens until the owner confirms it. */
export interface Proposal {
  id: string
  tool: string
  args: Record<string, unknown>
  title: string
  detail: string | null
}

/** `/api/ask`'s answer. */
export interface AskAnswer {
  text: string
  /** The tools behind the answer, for the "Used" chips. */
  used: string[]
  proposals: Proposal[]
  /** This month's AI spend and the cap, after this answer. */
  spent: number
  cap: number
}

export type ProposalState = 'waiting' | 'busy' | 'done' | 'cancelled' | 'failed'

export interface Card extends Proposal {
  state: ProposalState
  /** Why it failed, in the hub's words. */
  error?: string
}

export type Entry =
  | { kind: 'me'; text: string }
  | { kind: 'claude'; text: string; used: string[]; cards: Card[] }
  | { kind: 'error'; text: string }

export const SUGGESTIONS = [
  "How did last night's backup go?",
  "What's on the calendar tomorrow?",
  'Is anything broken right now?',
  'Turn off the living room lights',
]

/** What a card's outcome adds to Claude's side of the conversation, so a follow-up knows. */
function outcome(card: Card): string | null {
  if (card.state === 'done') return `(The owner confirmed: ${card.title}. It is done.)`
  if (card.state === 'cancelled') return `(The owner cancelled: ${card.title}.)`
  if (card.state === 'failed') return `(Confirmed, but it failed: ${card.title}. ${card.error ?? ''})`.trim()
  return null
}

/** The conversation as the hub reads it: the owner's questions and Claude's answers. */
export function history(entries: Entry[]): AskMessage[] {
  const out: AskMessage[] = []
  for (const entry of entries) {
    if (entry.kind === 'me') out.push({ role: 'user', text: entry.text })
    if (entry.kind === 'claude') {
      const notes = entry.cards.map(outcome).filter((n): n is string => Boolean(n))
      out.push({ role: 'assistant', text: [entry.text, ...notes].join('\n') })
    }
  }
  return out
}

/** "€0.42 of €10 this month"; the hub counts in dollars, which stay a little under euros. */
export function spendText(spent: number, cap: number, short = false): string {
  const money = (n: number) => `€${n >= 10 || Number.isInteger(n) ? n.toFixed(0) : n.toFixed(2)}`
  return short ? money(spent) : `${money(spent)} of ${money(cap)} this month`
}

export type Block = { kind: 'p'; parts: Part[] } | { kind: 'list'; items: Part[][] }
export type Part = { text: string; bold: boolean }

/** **bold** inside a line. */
export function parts(line: string): Part[] {
  return line
    .split(/(\*\*[^*]+\*\*)/)
    .filter(Boolean)
    .map((piece) =>
      piece.startsWith('**') && piece.endsWith('**') && piece.length > 4
        ? { text: piece.slice(2, -2), bold: true }
        : { text: piece, bold: false },
    )
}

/** The little formatting Claude is asked to use: paragraphs, "- " lists and **bold**. */
export function blocks(text: string): Block[] {
  const out: Block[] = []
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length) out.push({ kind: 'p', parts: parts(paragraph.join(' ')) })
    paragraph = []
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const item = /^[-*•]\s+(.*)$/.exec(line)
    if (item) {
      flush()
      const last = out[out.length - 1]
      if (last?.kind === 'list') last.items.push(parts(item[1]))
      else out.push({ kind: 'list', items: [parts(item[1])] })
    } else if (!line) {
      flush()
    } else {
      paragraph.push(line)
    }
  }
  flush()
  return out
}
