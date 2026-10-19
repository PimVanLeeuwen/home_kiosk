import { Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import { useEffect, useState, type CSSProperties } from 'react'
import type { Playing } from '../../lib/musicTypes'
import { useMusic } from '../../lib/useMusic'
import { Cover, Progress } from '../music/NowPlaying'
import { Pill } from '../ui/Pill'
import { Card } from './Card'

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

/** Now Playing on Home while something plays, or for two minutes after a pause. */
export function NowPlayingCard() {
  const { music, send } = useMusic(REFRESH_MS)
  const playing = music?.connected ? music.playing : null
  const pausedFor = usePausedFor(playing)
  if (!playing || (playing.state === 'paused' && pausedFor >= PAUSED_FOR_MS)) return null
  const on = playing.state === 'playing'
  const colour = playing.colour ?? '#9c8ffb'

  return (
    <Card
      title="Now playing"
      link={{ to: '/music', label: 'Music' }}
      actions={playing.device && <Pill tone="accent">On {playing.device.name}</Pill>}
    >
      <div style={{ '--np': colour } as CSSProperties} className="grid grid-cols-[96px_minmax(0,1fr)] items-center gap-4">
        <Cover item={playing} className="size-24 rounded-[12px] shadow-[0_10px_26px_color-mix(in_srgb,var(--np)_35%,transparent)]" />
        <div className="min-w-0">
          <h3 className="truncate text-[16px] font-semibold">{playing.title}</h3>
          <p className="truncate text-[13px] text-muted">
            {on ? '' : 'Paused · '}
            {playing.subtitle}
          </p>
          <Progress playing={playing} colour={colour} className="mt-3 [&_[role=progressbar]]:h-1 [&_div:last-child]:text-muted" />
          <div className="mt-1 flex items-center justify-end gap-3.5">
            <button type="button" aria-label="Previous" onClick={() => send('POST', '/api/music/control/previous', {})}>
              <SkipBack className="size-5" fill="currentColor" />
            </button>
            <button
              type="button"
              aria-label={on ? 'Pause' : 'Play'}
              onClick={() => send('POST', `/api/music/control/${on ? 'pause' : 'play'}`, {}, { state: on ? 'paused' : 'playing' })}
              className="grid size-[38px] place-items-center rounded-full bg-white text-[#111]"
            >
              {on ? <Pause className="size-[18px]" fill="currentColor" /> : <Play className="size-[18px]" fill="currentColor" />}
            </button>
            <button type="button" aria-label="Next" onClick={() => send('POST', '/api/music/control/next', {})}>
              <SkipForward className="size-5" fill="currentColor" />
            </button>
          </div>
        </div>
      </div>
    </Card>
  )
}
