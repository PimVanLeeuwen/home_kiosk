/** The colours a state can take across the hub, as CSS colour values. */
export type Tone = 'up' | 'down' | 'warn' | 'accent' | 'muted'

export const TONE_COLOR: Record<Tone, string> = {
  up: 'var(--color-up)',
  down: 'var(--color-down)',
  warn: 'var(--color-warn)',
  accent: 'var(--color-accent-line)',
  muted: 'var(--color-faint)',
}
