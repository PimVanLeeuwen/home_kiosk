import { Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { Playing } from '../../lib/musicTypes'
import type { HomeSend } from '../../lib/useHomeNowPlaying'
import { Cover, Progress } from '../music/NowPlaying'
import { Pill } from '../ui/Pill'
import { Card } from './Card'

/** Now Playing on Home, with what `useHomeNowPlaying` gives. */
export function NowPlayingCard({ playing, send }: { playing: Playing | null; send: HomeSend }) {
  if (!playing) return null
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
