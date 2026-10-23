import { Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { Playing } from '../../lib/musicTypes'
import type { HomeSend } from '../../lib/useHomeNowPlaying'
import { Cover, Progress } from '../music/NowPlaying'
import { Pill } from '../ui/Pill'
import { cn } from '../../lib/cn'
import { Card } from '../ui/Card'

interface Props {
  playing: Playing | null
  send: HomeSend
  /** Larger, as Home's hero. */
  hero?: boolean
}

/** Now Playing on Home, with what `useHomeNowPlaying` gives. */
export function NowPlayingCard({ playing, send, hero }: Props) {
  if (!playing) return null
  const on = playing.state === 'playing'
  const colour = playing.colour ?? '#9c8ffb'

  return (
    <Card
      title="Now playing"
      link={{ to: '/music', label: 'Music' }}
      actions={playing.device && <Pill tone="accent">On {playing.device.name}</Pill>}
    >
      <div
        style={{ '--np': colour } as CSSProperties}
        className={cn(
          'grid items-center gap-4',
          hero ? 'grid-cols-[96px_minmax(0,1fr)] md:grid-cols-[136px_minmax(0,1fr)] md:gap-7' : 'grid-cols-[96px_minmax(0,1fr)]',
        )}
      >
        <Cover
          item={playing}
          className={cn(
            'size-24 rounded-[12px] shadow-[0_10px_26px_color-mix(in_srgb,var(--np)_35%,transparent)]',
            hero && 'md:size-34 md:rounded-[14px] md:shadow-[0_18px_40px_-10px_color-mix(in_srgb,var(--np)_55%,transparent)]',
          )}
        />
        <div className="min-w-0">
          <h3 className={cn('truncate font-semibold', hero ? 'text-[20px] tracking-tight md:text-[34px]' : 'text-[16px]')}>{playing.title}</h3>
          <p className={cn('truncate text-muted', hero ? 'text-[14px] md:text-[15px]' : 'text-[13px]')}>
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
