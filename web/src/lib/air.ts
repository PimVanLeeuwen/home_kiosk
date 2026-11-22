import type { Air } from './types'

export type AirLevel = NonNullable<Air['level']>

/** Plan.md M17: the CO2 words and their colours. */
export const LEVEL: Record<AirLevel, { word: string; colour: string; className: string }> = {
  fresh: { word: 'Fresh', colour: 'var(--color-up)', className: 'text-up' },
  stuffy: { word: 'Getting stuffy', colour: 'var(--color-warn)', className: 'text-warn' },
  open_window: { word: 'Open a window', colour: 'var(--color-down)', className: 'text-down' },
}

/** Where CO2 turns stuffy, and where a window should open (ppm). */
export const STUFFY_FROM = 800
export const OPEN_FROM = 1200

/** "22,7": one decimal, a Dutch comma, as on the panel. */
export const degrees = (temperature: number) =>
  new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(temperature)
