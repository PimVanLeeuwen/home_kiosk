import { useEffect, useState } from 'react'
import type { Playing } from './musicTypes'
import { useMusic } from './useMusic'

/** Home asks less often than the Music page. */
const REFRESH_MS = 5_000
/** A paused item leaves Home after this long, as on the Home panel. */
const PAUSED_FOR_MS = 2 * 60_000

/** How long `playing` has been paused, by its own clock (React's pattern for state that follows a prop). */
function usePausedFor(playing: Playing | null | undefined): number {
  const key = playing?.state === 'paused' ? `${playing.title}|${playing.progress_ms}` : ''
  const [since, setSince] = useState({ key: '', at: 0 })
  const [now, setNow] = useState(() => new Date().getTime())
  useEffect(() => {
    if (!key) return
    const timer = window.setInterval(() => setNow(new Date().getTime()), 10_000)
    return () => window.clearInterval(timer)
  }, [key])
  if (since.key !== key) setSince({ key, at: new Date().getTime() })
  return key && since.key === key ? Math.max(0, now - since.at) : 0
}

export type HomeSend = ReturnType<typeof useMusic>['send']

/**
 * What Home shows as playing: the item while it plays, or for two minutes
 * after a pause; otherwise null.
 */
export function useHomeNowPlaying(): { playing: Playing | null; send: HomeSend } {
  const { music, send } = useMusic(REFRESH_MS)
  const playing = music?.connected ? music.playing : null
  const pausedFor = usePausedFor(playing)
  const gone = !playing || (playing.state === 'paused' && pausedFor >= PAUSED_FOR_MS)
  return { playing: gone ? null : playing, send }
}
