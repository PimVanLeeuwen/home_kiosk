/** Shapes of `/api/music` (collector app/sources/music.py). */

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
}

export interface Playlist {
  id: string
  name: string
  cover: string | null
  owner: string | null
}

export const coverUrl = (key: string) => `/api/music/covers/${key}`

/** "1:37", "58:12". */
export function minutes(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
