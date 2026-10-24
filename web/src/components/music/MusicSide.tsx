import { Laptop, Play, Smartphone, Speaker, Tv } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import type { Favourite, MusicDevice } from '../../lib/musicTypes'
import { Cover } from './NowPlaying'
import { Surface } from '../ui/Card'

const ICON = { computer: Laptop, smartphone: Smartphone, tv: Tv } as const
const TYPE: Record<string, string> = { computer: 'Computer', smartphone: 'Phone', tv: 'TV', speaker: 'Speaker', avr: 'Receiver', castvideo: 'Chromecast' }

function Label({ children, aside }: { children: string; aside?: string }) {
  return (
    <p className="mb-2.5 flex justify-between gap-2.5 text-label font-semibold tracking-[0.07em] text-faint uppercase">
      {children}
      {aside && <b className="truncate font-medium tracking-normal text-muted normal-case">{aside}</b>}
    </p>
  )
}

interface Props {
  devices: MusicDevice[]
  favourites: Favourite[]
  /** The favourite that is being started, while it is. */
  starting: number | null
  onTransfer: (device: MusicDevice) => void
  onFavourite: (favourite: Favourite) => void
}

/** Your Spotify devices (tap one to move playback there) and the four favourites. */
export function MusicSide({ devices, favourites, starting, onTransfer, onFavourite }: Props) {
  const active = devices.find((d) => d.active)
  return (
    <Surface as="section" aria-label="Devices and favourites">
      <Label aside={active ? `Playing on ${active.name}` : 'None active'}>Devices</Label>
      {devices.length ? (
        <ul className="mb-[18px] grid gap-1.5">
          {devices.map((d) => {
            const Icon = ICON[d.type as keyof typeof ICON] ?? Speaker
            return (
              <li key={d.id ?? d.name}>
                <button
                  type="button"
                  disabled={d.active || d.restricted || !d.id}
                  onClick={() => onTransfer(d)}
                  aria-label={d.active ? `${d.name}: playing here` : `Move playback to ${d.name}`}
                  className={cn(
                    'grid w-full grid-cols-[30px_1fr_auto] items-center gap-2.5 rounded-[11px] border px-[11px] py-[9px] text-left',
                    d.active ? 'border-up/45 bg-linear-to-r from-up/12 to-transparent to-70%' : 'border-glass-line bg-glass hover:border-faint',
                  )}
                >
                  <span aria-hidden="true" className="grid size-[30px] place-items-center rounded-[8px] bg-white/6 text-muted">
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate">{d.name}</span>
                    <small className="block text-label text-faint">{TYPE[d.type] ?? 'Device'}</small>
                  </span>
                  <span className={cn('text-label', d.active ? 'text-up' : 'text-faint')}>{d.active ? 'Playing here' : 'Move here'}</span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="mb-[18px] text-small text-muted">No Spotify devices right now: open Spotify on a phone, Mac or the Apple TV.</p>
      )}

      <Label aside="Settings → Music">Favourites</Label>
      {favourites.length ? (
        <ul className="grid grid-cols-2 gap-2.5">
          {favourites.map((f) => (
            <li key={f.position}>
              <button
                type="button"
                disabled={starting !== null}
                onClick={() => onFavourite(f)}
                aria-label={`Play ${f.name}`}
                aria-busy={starting === f.position}
                className="relative flex aspect-[1.45] w-full items-end overflow-hidden rounded-[14px] px-3 py-2.5 text-left text-white disabled:cursor-wait"
              >
                <Cover item={f} className="absolute inset-0 size-full" />
                <span aria-hidden="true" className="absolute inset-0 bg-linear-to-b from-transparent from-45% to-black/60" />
                <span className="relative text-small font-semibold">{f.name}</span>
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-2.5 right-2.5 grid size-[30px] place-items-center rounded-full bg-white/90 text-[#111]',
                    starting === f.position && 'motion-safe:animate-pulse',
                  )}
                >
                  <Play className="size-4" fill="currentColor" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-small text-muted">
          No favourites yet: choose four in{' '}
          <Link to="/settings/music" className="text-accent-fg hover:underline">
            Settings → Music
          </Link>
          .
        </p>
      )}
    </Surface>
  )
}
