import { useCallback, useEffect, useState } from 'react'
import { ApiError, sendJson } from './api'
import type { Music, Playing } from './musicTypes'
import { useApi } from './useApi'

/** While a page or card shows music; the hub itself only asks Spotify then. */
const REFRESH_MS = 2_000
/** How long a change is shown before the reported state wins again. */
const HOLD_MS = 5_000

type Hold = { state?: Playing['state']; volume?: number; device?: string; until: number }

/**
 * `/api/music` with the controls. A change shows at once and is held until
 * Spotify reports it (or for five seconds), as on the Lights page, so play and
 * pause do not flip back while Spotify catches up.
 */
export function useMusic(refreshMs = REFRESH_MS) {
  const api = useApi<Music>('/api/music', refreshMs)
  const [hold, setHold] = useState<Hold | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { reload } = api

  const reported = api.data
  const confirmed =
    hold &&
    reported &&
    (hold.state === undefined || reported.playing?.state === hold.state) &&
    (hold.volume === undefined || reported.playing?.device?.volume === hold.volume) &&
    (hold.device === undefined || reported.devices.some((d) => d.id === hold.device && d.active))

  // Let go once Spotify confirms or the hold runs out; from a timer, not the render.
  useEffect(() => {
    if (!hold) return
    const timer = window.setTimeout(() => setHold(null), confirmed ? 0 : Math.max(0, hold.until - new Date().getTime()))
    return () => window.clearTimeout(timer)
  }, [hold, confirmed])

  const music = reported && hold ? applyHold(reported, hold) : reported

  const send = useCallback(
    async (method: 'POST' | 'PUT', path: string, body: object, change: Omit<Hold, 'until'> = {}) => {
      if (Object.keys(change).length) setHold({ ...change, until: new Date().getTime() + HOLD_MS })
      setFailure(null)
      setBusy(true)
      try {
        return await sendJson<Record<string, unknown>>(method, path, body)
      } catch (err) {
        setHold(null)
        setFailure(err instanceof ApiError ? err.message : 'Spotify did not take the change.')
        return null
      } finally {
        setBusy(false)
        reload()
      }
    },
    [reload],
  )

  return { ...api, music, failure, busy, send }
}

function applyHold(music: Music, hold: Hold): Music {
  const playing = music.playing && {
    ...music.playing,
    state: hold.state ?? music.playing.state,
    device: music.playing.device && hold.volume !== undefined ? { ...music.playing.device, volume: hold.volume } : music.playing.device,
  }
  const devices = hold.device ? music.devices.map((d) => ({ ...d, active: d.id === hold.device })) : music.devices
  return { ...music, playing, devices }
}

/**
 * The progress of what plays, moving on its own between polls: the position
 * Spotify reported plus the time since that answer came in.
 */
export function useProgress(playing: Playing | null | undefined): number {
  // What Spotify reported, not the object: a held change makes a new object per render.
  const key = playing ? `${playing.title}|${playing.progress_ms}|${playing.state}` : ''
  const [received, setReceived] = useState({ key: '', at: 0 })
  const [now, setNow] = useState(() => new Date().getTime())
  useEffect(() => {
    if (playing?.state !== 'playing') return
    const timer = window.setInterval(() => setNow(new Date().getTime()), 1_000)
    return () => window.clearInterval(timer)
  }, [playing?.state])
  // A new answer: note when it came in (React's pattern for state that follows a prop).
  if (received.key !== key) setReceived({ key, at: new Date().getTime() })
  if (!playing) return 0
  const moved = playing.state === 'playing' && received.key === key ? Math.max(0, now - received.at) : 0
  return Math.min(playing.duration_ms, playing.progress_ms + moved)
}
