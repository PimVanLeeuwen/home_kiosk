import { Pause, Play, SkipBack, SkipForward, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { coverUrl, minutes, type MusicItem, type Playing } from '../../lib/musicTypes'
import { useProgress } from '../../lib/useMusic'

const VIOLET = 'var(--color-data-violet)'
/** A volume is sent once the slider has rested this long. */
const SETTLE_MS = 300

/** The cover, or a tile in its colour when Spotify has none. */
export function Cover({ item, className }: { item: Pick<MusicItem, 'cover' | 'colour'>; className?: string }) {
  const colour = item.colour ?? VIOLET
  return item.cover ? (
    <img src={coverUrl(item.cover)} alt="" className={cn('object-cover', className)} />
  ) : (
    <span
      aria-hidden="true"
      className={cn('block', className)}
      style={{ background: `radial-gradient(circle at 30% 28%, ${colour}, transparent 62%), linear-gradient(135deg, #2a2440, #111)` }}
    />
  )
}

export function Equaliser({ playing, className }: { playing: boolean; className?: string }) {
  return (
    <span aria-hidden="true" className={cn('flex h-[22px] items-end gap-[3px]', className)}>
      {[0, -0.3, -0.6, -0.15].map((delay) => (
        <i
          key={delay}
          className={cn('block h-[5px] w-1 rounded-[2px] bg-white', playing ? 'motion-safe:animate-eq' : 'opacity-60')}
          style={{ animationDelay: `${delay}s` }}
        />
      ))}
    </span>
  )
}

export function Progress({ playing, colour, className }: { playing: Playing; colour: string; className?: string }) {
  const at = useProgress(playing)
  const share = playing.duration_ms ? (at / playing.duration_ms) * 100 : 0
  return (
    <div className={className}>
      <div
        role="progressbar"
        aria-label="Progress"
        aria-valuemin={0}
        aria-valuemax={Math.round(playing.duration_ms / 1000)}
        aria-valuenow={Math.round(at / 1000)}
        aria-valuetext={`${minutes(at)} of ${minutes(playing.duration_ms)}`}
        className="h-[5px] rounded-full bg-white/18"
      >
        <i
          style={{ width: `${share.toFixed(1)}%`, '--pc': colour } as CSSProperties}
          className="relative block h-full rounded-full bg-white shadow-[0_0_10px_var(--pc)] after:absolute after:top-[-4px] after:right-[-6px] after:size-[13px] after:rounded-full after:bg-white after:shadow-[0_0_12px_var(--pc)]"
        />
      </div>
      <div className="mt-[7px] flex justify-between text-[12px] text-white/70">
        <span>{minutes(at)}</span>
        <span>{minutes(playing.duration_ms)}</span>
      </div>
    </div>
  )
}

interface Props {
  playing: Playing
  onControl: (action: 'play' | 'pause' | 'next' | 'previous') => void
  onVolume: (percent: number) => void
}

/** The Home panel's Now Playing as the top of the Music page. */
export function NowPlaying({ playing, onControl, onVolume }: Props) {
  const colour = playing.colour ?? VIOLET
  const on = playing.state === 'playing'
  const [dragging, setDragging] = useState<number | null>(null)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const volume = dragging ?? playing.device?.volume ?? null

  function setVolume(value: number) {
    setDragging(value)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      onVolume(value)
      setDragging(null)
    }, SETTLE_MS)
  }

  return (
    <section
      aria-label="Now playing"
      data-state={playing.state}
      className="relative flex min-h-0 flex-col overflow-hidden rounded-[18px] border border-glass-line px-[18px] py-5 md:min-h-[380px] md:px-7 md:pt-[26px] md:pb-6"
    >
      <div
        aria-hidden="true"
        className="absolute -inset-[10%] opacity-90 blur-[30px] after:absolute after:inset-0 after:bg-linear-to-b after:from-[rgb(10_10_14/0.2)] after:to-[rgb(10_10_14/0.75)]"
        style={{ background: `radial-gradient(70% 60% at 30% 25%, color-mix(in srgb, ${colour} 55%, transparent), transparent 70%), radial-gradient(70% 70% at 80% 80%, color-mix(in srgb, ${colour} 35%, #000), transparent 70%), #17141f` }}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div
          className="relative h-[150px] w-[240px] md:h-[190px] md:w-[300px]"
          style={{ '--glow': `color-mix(in srgb, ${colour} 45%, transparent)` } as CSSProperties}
        >
          <span
            aria-hidden="true"
            className={cn(
              'absolute top-[7px] grid size-[136px] place-items-center rounded-full bg-[repeating-radial-gradient(circle,#0c0c0f_0_2.5px,#18171d_2.5px_4.5px)] shadow-[0_10px_30px_rgb(0_0_0/0.6),inset_0_0_0_1px_rgb(255_255_255/0.06)] transition-[left] duration-700 md:top-2 md:size-[174px]',
              on ? 'left-[72px] md:left-[92px] motion-safe:animate-[spin_4s_linear_infinite]' : 'left-[30px] md:left-10',
            )}
          >
            <Cover item={playing} className="size-[46px] rounded-full md:size-[58px]" />
          </span>
          <Cover
            item={playing}
            className="relative z-[1] size-[150px] rounded-[16px] shadow-[0_14px_40px_var(--glow),0_8px_20px_rgb(0_0_0/0.5)] md:size-[190px]"
          />
        </div>
        {playing.device && (
          // On a phone the Devices list below says where it plays; the chip would cover the record.
          <span className="hidden items-center gap-[7px] rounded-full border border-white/18 bg-white/12 px-3 py-1.5 text-[12.5px] whitespace-nowrap text-white backdrop-blur-[8px] sm:inline-flex">
            <i aria-hidden="true" className="size-[7px] rounded-full bg-up shadow-[0_0_6px_var(--color-up)]" />
            {playing.device.name}
          </span>
        )}
      </div>

      <div className="relative mt-[22px] flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[21px] leading-[1.15] font-semibold tracking-[-0.015em] text-white md:text-[26px]">{playing.title}</h2>
          <p className="mt-1 text-[15px] text-white/75">
            {playing.state === 'paused' && 'Paused · '}
            {playing.subtitle}
          </p>
        </div>
        <Equaliser playing={on} />
      </div>

      <Progress playing={playing} colour={colour} className="relative mt-[22px]" />

      <div className="relative mt-3 flex items-center justify-center gap-[30px] text-white">
        <button type="button" aria-label="Previous" onClick={() => onControl('previous')} className="grid place-items-center">
          <SkipBack className="size-[26px]" fill="currentColor" />
        </button>
        <button
          type="button"
          aria-label={on ? 'Pause' : 'Play'}
          onClick={() => onControl(on ? 'pause' : 'play')}
          style={{ boxShadow: `0 0 28px color-mix(in srgb, ${colour} 60%, transparent)` }}
          className="grid size-[62px] place-items-center rounded-full bg-white text-[#111]"
        >
          {on ? <Pause className="size-6" fill="currentColor" /> : <Play className="size-6" fill="currentColor" />}
        </button>
        <button type="button" aria-label="Next" onClick={() => onControl('next')} className="grid place-items-center">
          <SkipForward className="size-[26px]" fill="currentColor" />
        </button>
      </div>

      {volume !== null && (
        <label className="relative mt-4 flex items-center gap-2.5 text-[12px] text-white/75">
          <Volume2 aria-hidden="true" className="size-4" />
          <span className="sr-only">Volume</span>
          <input
            type="range"
            min={0}
            max={100}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            style={{ '--p': `${volume}%` } as CSSProperties}
            className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-[linear-gradient(90deg,rgb(255_255_255/0.85)_var(--p),rgb(255_255_255/0.18)_var(--p))] [&::-webkit-slider-thumb]:size-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
          />
          <span aria-hidden="true">{volume}%</span>
        </label>
      )}
    </section>
  )
}

/** When nothing plays: what played last, and where to start. */
export function NothingPlaying({ last, defaultDevice }: { last: MusicItem | null; defaultDevice: string }) {
  return (
    <section aria-label="Now playing" data-state="idle" className="rounded-[18px] border border-glass-line bg-card px-[18px] py-5 md:min-h-[380px] md:px-7 md:pt-[26px]">
      <p className="text-[11.5px] font-semibold tracking-[0.07em] text-faint uppercase">Now playing</p>
      <h2 className="mt-[18px] text-[22px] font-semibold">Nothing playing</h2>
      <p className="text-muted">Start a favourite: it plays on {defaultDevice}, or play on any of your devices.</p>
      {last && (
        <div className="mt-[18px] flex items-center gap-3 rounded-[12px] border border-glass-line bg-glass p-2.5">
          <Cover item={last} className="size-[46px] flex-none rounded-[9px]" />
          <div className="min-w-0">
            <b className="block truncate text-[14px]">{last.title}</b>
            <span className="block truncate text-[12.5px] text-muted">Played last{last.subtitle ? ` · ${last.subtitle}` : ''}</span>
          </div>
        </div>
      )}
    </section>
  )
}
