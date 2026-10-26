import { Play } from 'lucide-react'
import type { CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import type { RecentMusic } from '../../lib/musicTypes'
import { Surface } from '../ui/Card'
import { Cover, Equaliser } from './NowPlaying'

interface Props {
  recent: RecentMusic[]
  /** What plays now comes from this uri (`Playing.context`). */
  playingFrom: string | null
  /** The one being started, while it is. */
  starting: number | null
  onPlay: (index: number) => void
  /** Spotify makes the hub wait: nothing can be started until then. */
  waiting?: boolean
}

/**
 * The playlists and albums played lately, as on the Home panel's cover wall
 * (plan.md M27, M): each a tap to play it again from the start; the one that
 * plays has a rim and its equaliser.
 */
export function PlayedLately({ recent, playingFrom, starting, onPlay, waiting = false }: Props) {
  return (
    <Surface as="section" aria-labelledby="played-lately" className="lg:col-start-1">
      <h2 id="played-lately" className="mb-2.5 text-label font-semibold tracking-[0.07em] text-faint uppercase">
        Played lately
      </h2>
      {recent.length ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {recent.map((r, i) => {
            const plays = r.uri === playingFrom
            return (
              <li key={r.uri}>
                <button
                  type="button"
                  disabled={waiting || starting !== null}
                  onClick={() => onPlay(i)}
                  aria-label={plays ? `${r.name}: playing` : `Play ${r.name}`}
                  aria-busy={starting === i}
                  className={cn('pressable group grid w-full gap-2 text-left disabled:cursor-wait', waiting && 'opacity-50 disabled:cursor-default')}
                >
                  <span
                    className={cn(
                      'relative block aspect-square overflow-hidden rounded-[14px]',
                      plays && 'shadow-[0_0_28px_-6px_var(--c)] ring-2 ring-white/85',
                    )}
                    style={{ '--c': r.colour ?? 'var(--color-data-violet)' } as CSSProperties}
                  >
                    <Cover item={r} className="absolute inset-0 size-full" />
                    {plays ? (
                      <span className="absolute right-2 bottom-2 grid place-items-center rounded-[9px] bg-black/60 px-2 py-1.5">
                        <Equaliser playing />
                      </span>
                    ) : (
                      <span
                        aria-hidden="true"
                        className={cn(
                          'absolute right-2 bottom-2 grid size-[30px] place-items-center rounded-full bg-white/90 text-[#111] opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100',
                          starting === i && 'opacity-100 motion-safe:animate-pulse',
                        )}
                      >
                        <Play className="size-4" fill="currentColor" />
                      </span>
                    )}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-small font-semibold">{r.name}</span>
                    <small className="block text-label text-faint">{r.kind === 'album' ? 'Album' : 'Playlist'}</small>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="text-small text-muted">
          {waiting ? 'What you played shows again once Spotify lets the hub ask.' : 'Nothing played lately: what you play from a playlist or an album shows here.'}
        </p>
      )}
    </Surface>
  )
}
