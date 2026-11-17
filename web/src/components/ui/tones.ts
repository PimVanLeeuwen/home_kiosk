/** The colours a state can take across the hub, as CSS colour values. */
export type Tone = 'up' | 'down' | 'warn' | 'accent' | 'muted'

export const TONE_COLOR: Record<Tone, string> = {
  up: 'var(--color-up)',
  down: 'var(--color-down)',
  warn: 'var(--color-warn)',
  accent: 'var(--color-accent-line)',
  muted: 'var(--color-faint)',
}

/** A tone as a tinted label: its colour on a faint wash of itself (Pill, Tag). */
export const TONE_TINT: Record<Tone, string> = {
  up: 'text-up bg-up/13',
  down: 'text-down bg-down/14',
  warn: 'text-warn bg-warn/15',
  accent: 'text-accent-fg bg-accent/20',
  muted: 'text-muted bg-raised',
}

/** A tone as an outlined label: its colour and a thin edge, no wash. */
export const TONE_OUTLINE: Record<Tone, string> = {
  up: 'text-up border-up/30',
  down: 'text-down border-down/40',
  warn: 'text-warn border-warn/35',
  accent: 'text-accent-fg border-accent-line/30',
  muted: 'text-muted border-glass-line',
}
