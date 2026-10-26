/** Shapes of `/api/music` (collector app/sources/music.py). */

import { formatTime, formatWhen } from './format'

export interface MusicDevice {
  id: string | null
  name: string
  type: string
  active: boolean
  volume: number | null
  restricted: boolean
}

export interface MusicItem {
  kind: 'track' | 'episode'
  title: string
  subtitle: string | null
  duration_ms: number
  /** Key for `/api/music/covers/<key>`, or null without a cover. */
  cover: string | null
  /** The cover's main colour, for the glow. */
  colour: string | null
}

export interface Playing extends MusicItem {
  state: 'playing' | 'paused'
  progress_ms: number
  device: MusicDevice | null
  /** The playlist or album it plays from (a Spotify uri), when Spotify says. */
  context?: string | null
}

/** One of the playlists or albums played lately (plan.md M27, M). */
export interface RecentMusic {
  /** Its Spotify uri: what plays matches it with `Playing.context`. */
  uri: string
  kind: 'playlist' | 'album'
  name: string
  cover: string | null
  colour: string | null
}

export interface Favourite {
  position: number
  id: string
  name: string
  cover: string | null
  colour: string | null
}

export interface Music {
  /** Epoch seconds on the hub. */
  as_of: number
  stale: boolean
  connected: boolean
  default_device: string
  playing: Playing | null
  devices: MusicDevice[]
  favourites: Favourite[]
  last: MusicItem | null
  /** The last four different playlists or albums played from, favourites left out. */
  recent?: RecentMusic[]
  /** While Spotify makes the hub wait (a 429): until when, epoch seconds; the controls wait too. */
  paused_until?: number | null
}

export interface Playlist {
  id: string
  name: string
  cover: string | null
  owner: string | null
}

/** "Spotify paused the hub until 16:52" ("until Mon 26 Oct 09:12" on another day). */
export function pauseNote(until: number, now = new Date()): string {
  const end = new Date(until * 1000)
  const sameDay = end.toDateString() === now.toDateString()
  return `Spotify paused the hub until ${sameDay ? formatTime(end.toISOString()) : formatWhen(end.toISOString(), now)}`
}

export const coverUrl = (key: string) => `/api/music/covers/${key}`

/** "1:37", "58:12". */
export function minutes(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
