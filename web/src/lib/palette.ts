import { Box, FileText, FolderGit2, LayoutGrid, Lightbulb, LightbulbOff, Pause, Play, SkipForward, type LucideIcon } from 'lucide-react'
import { fold, fuzzyScore } from './fuzzy'
import { iconUrl } from './icons'
import { serviceHref } from './links'
import { NAV_ITEMS } from './navigation'
import { SETTINGS_SECTIONS } from './settingsSections'
import { formatDate } from './format'
import type { DockerOverview, DocumentSearch, Hosts, ReposResponse, ServicesResponse } from './types'

/** Something the command palette can go to. */
export interface PaletteItem {
  /** Stable across visits: recent choices are kept by it. */
  id: string
  group: 'Actions' | 'Pages' | 'Settings' | 'Services' | 'Repos' | 'Containers' | 'Documents'
  label: string
  /** A short line beside the label. */
  hint?: string
  /** More words to match on that are not shown. */
  keywords?: string
  icon: LucideIcon
  /** A bundled service icon, shown instead of `icon`. */
  image?: string
  /** A page of the hub, or a link that opens in a new tab. */
  to?: string
  href?: string
  /** Data rows (services, repos, containers) only show once something is typed, or as recent. */
  searchOnly?: boolean
  /** A write through one of the hub's own endpoints, and what to say when it worked. */
  action?: { path: string; body: unknown; done: string }
}

/**
 * The palette's few actions (plan.md M25), through the endpoints the Lights and
 * Music pages use. Nothing that deletes or imports.
 */
export const ACTIONS: PaletteItem[] = [
  { id: 'action:lights-on', group: 'Actions', label: 'Lights on', hint: 'Living room', keywords: 'hue switch', icon: Lightbulb, action: { path: '/api/lights/room', body: { on: true }, done: 'The living room lights are on.' } },
  { id: 'action:lights-off', group: 'Actions', label: 'Lights off', hint: 'Living room', keywords: 'hue switch', icon: LightbulbOff, action: { path: '/api/lights/room', body: { on: false }, done: 'The living room lights are off.' } },
  { id: 'action:play', group: 'Actions', label: 'Play', hint: 'Spotify', keywords: 'music resume', icon: Play, action: { path: '/api/music/control/play', body: {}, done: 'Playing.' } },
  { id: 'action:pause', group: 'Actions', label: 'Pause', hint: 'Spotify', keywords: 'music stop', icon: Pause, action: { path: '/api/music/control/pause', body: {}, done: 'Paused.' } },
  { id: 'action:next', group: 'Actions', label: 'Next track', hint: 'Spotify', keywords: 'music skip song', icon: SkipForward, action: { path: '/api/music/control/next', body: {}, done: 'Skipped to the next track.' } },
]

export const RECENT_KEY = 'hub.palette.recent'
const RECENT_MAX = 5
const RESULTS_MAX = 40

/** The actions, every page and every Settings section: always there, whatever the hub answers. */
export function staticItems(): PaletteItem[] {
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
  return [...ACTIONS, ...pages, ...settings]
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
    const rest = items.filter((i) => !recents.includes(i) && !i.searchOnly)
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

export interface PaletteData {
  services?: ServicesResponse
  repos?: ReposResponse
  docker?: DockerOverview
  hosts?: Hosts
}

/**
 * The services (opened as their tiles open them), the repos on GitHub, and the
 * containers, whose logs open in Dozzle (its /show?name= page finds the newest
 * container of that name). Containers only when Dozzle is in the catalog.
 */
export function dataItems({ services, repos, docker, hosts }: PaletteData, pageHost: string): PaletteItem[] {
  const all = services?.groups.flatMap((g) => g.services) ?? []
  const serviceRows = all
    .filter((s) => s.url || s.port)
    .map(
      (s): PaletteItem => ({
        id: `service:${s.id}`,
        group: 'Services',
        label: s.name,
        hint: s.description,
        keywords: s.group,
        icon: LayoutGrid,
        image: iconUrl(s.icon),
        href: serviceHref(s, pageHost, hosts),
        searchOnly: true,
      }),
    )
  const repoRows = (repos?.groups ?? []).flatMap((g) =>
    g.repos.map(
      (r): PaletteItem => ({
        id: `repo:${r.full_name}`,
        group: 'Repos',
        label: r.name,
        hint: [g.label, r.description].filter(Boolean).join(' · '),
        keywords: `repo ${r.full_name}`,
        icon: FolderGit2,
        href: r.url,
        searchOnly: true,
      }),
    ),
  )
  const dozzle = all.find((s) => s.container === 'dozzle' && s.port)
  const containerRows = dozzle
    ? (docker?.containers ?? []).map(
        (c): PaletteItem => ({
          id: `container:${c.name}`,
          group: 'Containers',
          label: c.name,
          // The stack says why a search for "kiosk" finds readeck.
          hint: ['Logs in Dozzle', c.project !== c.name && c.project, c.state !== 'running' && c.state].filter(Boolean).join(' · '),
          keywords: ['logs container', c.project].filter(Boolean).join(' '),
          icon: Box,
          href: serviceHref({ ...dozzle, path: `/show?name=${encodeURIComponent(c.name)}` }, pageHost, hosts),
          searchOnly: true,
        }),
      )
    : []
  return [...serviceRows, ...repoRows, ...containerRows]
}

/** Typed letters before the palette asks Paperless, and the pause in typing it waits for. */
export const DOCUMENTS_FROM = 3
export const DOCUMENTS_DELAY_MS = 250

/**
 * Paperless's matches (title and content), opened on its document page. They
 * come as Paperless ranked them, after the hub's own rows; without Paperless in
 * the catalog there is nowhere to open them, so none.
 */
export function documentItems(found: DocumentSearch | undefined, { services, hosts }: PaletteData, pageHost: string): PaletteItem[] {
  const paperless = services?.groups.flatMap((g) => g.services).find((s) => s.widget === 'paperless' && s.port)
  if (!found?.available || !paperless) return []
  return found.results.map((d) => ({
    id: `document:${d.id}`,
    group: 'Documents',
    label: d.title,
    hint: [d.correspondent, // Noon, so the day never shifts with the time zone.
      d.created && formatDate(`${d.created}T12:00`)].filter(Boolean).join(' · ') || 'Paperless',
    icon: FileText,
    href: serviceHref({ ...paperless, path: `/documents/${d.id}/details` }, pageHost, hosts),
    searchOnly: true,
  }))
}
