import type { LucideIcon } from 'lucide-react'
import { fold, fuzzyScore } from './fuzzy'
import { NAV_ITEMS } from './navigation'
import { SETTINGS_SECTIONS } from './settingsSections'

/** Something the command palette can go to. */
export interface PaletteItem {
  /** Stable across visits: recent choices are kept by it. */
  id: string
  group: 'Pages' | 'Settings'
  label: string
  /** A short line beside the label. */
  hint?: string
  /** More words to match on that are not shown. */
  keywords?: string
  icon: LucideIcon
  to: string
}

export const RECENT_KEY = 'hub.palette.recent'
const RECENT_MAX = 5
const RESULTS_MAX = 40

export function pageItems(): PaletteItem[] {
  const pages = NAV_ITEMS.map(
    (item): PaletteItem => ({ id: `page:${item.to}`, group: 'Pages', label: item.label, hint: item.description, icon: item.icon, to: item.to }),
  )
  const settings = SETTINGS_SECTIONS.map(
    (s): PaletteItem => ({
      id: `settings:${s.slug}`,
      group: 'Settings',
      label: s.label,
      hint: 'Settings',
      keywords: 'settings',
      icon: s.icon,
      to: `/settings/${s.slug}`,
    }),
  )
  return [...pages, ...settings]
}

export function loadRecent(): string[] {
  try {
    const ids: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]')
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string').slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

export function saveRecent(id: string): void {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify([id, ...loadRecent().filter((r) => r !== id)].slice(0, RECENT_MAX)))
  } catch {
    // Private browsing without storage: the palette just has no recents.
  }
}

export interface PaletteRow {
  item: PaletteItem
  /** The heading shown above the first row of each group, without a query. */
  heading?: string
}

/**
 * The rows for a query. Without one: recent choices first, then every page and
 * section in the sidebar's order. With one: the matches best first (the label
 * counts most, and only it matches scattered letters), a recent choice a little
 * ahead of an equal match.
 */
export function search(items: PaletteItem[], query: string, recent: string[]): PaletteRow[] {
  if (!query.trim()) {
    const recents = recent.map((id) => items.find((i) => i.id === id)).filter((i): i is PaletteItem => !!i)
    const rest = items.filter((i) => !recents.includes(i))
    const rows: PaletteRow[] = recents.map((item, n) => ({ item, heading: n === 0 ? 'Recent' : undefined }))
    let last: string | undefined
    for (const item of rest) {
      rows.push({ item, heading: item.group !== last ? item.group : undefined })
      last = item.group
    }
    return rows
  }
  const scored = items.flatMap((item) => {
    const label = fuzzyScore(query, item.label)
    // Beyond the label, each word typed has to be there as written: scattered letters in a description match anything.
    const text = [item.keywords, item.label, item.hint].filter(Boolean).join(' ')
    const words = fold(query).split(/\s+/).filter(Boolean)
    const extra = words.every((w) => fold(text).includes(w)) ? fuzzyScore(query, text) : null
    const best = Math.max(label ?? -Infinity, extra == null ? -Infinity : extra * 0.6)
    if (best === -Infinity) return []
    const bonus = recent.includes(item.id) ? 1.5 - recent.indexOf(item.id) * 0.2 : 0
    return [{ item, score: best + bonus }]
  })
  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, RESULTS_MAX)
    .map(({ item }) => ({ item }))
}

/** The palette's shortcut as this computer writes it: ⌘K on a Mac, Ctrl K elsewhere. */
export const shortcutLabel = (platform = typeof navigator === 'undefined' ? '' : navigator.platform) =>
  /Mac|iPhone|iPad/.test(platform) ? '⌘K' : 'Ctrl K'

/** ⌘K or Ctrl-K, whatever the keyboard layout's shift state. */
export const isPaletteKey = (e: { key: string; metaKey: boolean; ctrlKey: boolean; altKey: boolean }) =>
  (e.metaKey || e.ctrlKey) && !e.altKey && e.key.toLowerCase() === 'k'
