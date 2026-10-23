import type { CSSProperties, ReactNode } from 'react'
import { curve, H, orbs, threadLinks, W, zones, type Orb } from '../../lib/applePlan'
import { cn } from '../../lib/cn'
import type { AppleDevices, ApplePlaying } from '../../lib/types'
import { Pill } from '../ui/Pill'
import { Card } from '../ui/Card'
import { StaleNote } from '../ui/states'

const VIDEO = '#5aa9ff'
const MUSIC = '#b4a9ff'
const AMBER = '#f0bd5a'

type Room = AppleDevices['rooms'][number]

const colourOf = (p: ApplePlaying) => (p.media === 'video' ? VIDEO : MUSIC)

function Glyph({ o }: { o: Orb }) {
  const { x, y } = o
  if (o.device.kind === 'tv')
    return (
      <>
        <rect x={x - 2.8} y={y - 1.9} width={5.6} height={3.6} rx={0.8} fill="none" stroke="currentColor" strokeWidth={0.6} />
        <path d={`M${x - 1.2} ${y + 2.7}h2.4`} stroke="currentColor" strokeWidth={0.6} strokeLinecap="round" />
      </>
    )
  if (o.device.kind === 'homepod')
    return <rect x={x - 2} y={y - 2.7} width={4} height={5.4} rx={1.9} fill="none" stroke="currentColor" strokeWidth={0.6} />
  return (
    <>
      <circle cx={x} cy={y} r={2} fill="none" stroke="currentColor" strokeWidth={0.6} />
      <circle cx={x} cy={y - 0.2} r={0.7} fill="currentColor" />
    </>
  )
}

/**
 * Which devices send out ripples: the room's HomePods (a stereo pair plays as
 * one) and, for video, its Apple TV too.
 */
function plays(o: Orb): boolean {
  const p = o.room.playing
  if (!p || p.state !== 'playing' || !o.device.online) return false
  return o.device.kind !== 'tv' || p.media === 'video' || o.device.id === p.device
}

function Plan({ rooms }: { rooms: Room[] }) {
  const zs = zones(rooms)
  const all = orbs(zs)
  const links = threadLinks(all)
  const broken = (o: Orb) => !o.device.online || o.device.thread === false
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={planLabel(rooms)} className="mx-auto block h-auto w-full max-w-[520px]">
      <defs>
        {zs.map(
          (z) =>
            z.room.playing && (
              <radialGradient key={z.room.id} id={`apple-glow-${z.room.id}`} cx="50%" cy="45%" r="70%">
                <stop offset="0" stopColor={colourOf(z.room.playing)} stopOpacity={z.room.playing.state === 'playing' ? 0.22 : 0.12} />
                <stop offset="1" stopColor={colourOf(z.room.playing)} stopOpacity={0} />
              </radialGradient>
            ),
        )}
        <radialGradient id="apple-orb">
          <stop offset="0" stopColor="rgb(255 255 255 / 0.22)" />
          <stop offset="1" stopColor="rgb(255 255 255 / 0.03)" />
        </radialGradient>
        {[
          ['video', VIDEO, 0.45],
          ['music', MUSIC, 0.45],
          ['amber', AMBER, 0.3],
        ].map(([id, colour, opacity]) => (
          <radialGradient key={id} id={`apple-halo-${id}`}>
            <stop offset="0" stopColor={colour as string} stopOpacity={opacity} />
            <stop offset="1" stopColor={colour as string} stopOpacity={0} />
          </radialGradient>
        ))}
      </defs>

      {zs.map((z) => {
        const colour = z.room.playing && colourOf(z.room.playing)
        return (
          <g key={z.room.id} data-room={z.room.id} data-playing={z.room.playing?.state ?? 'none'}>
            <rect
              x={z.x}
              y={z.y}
              width={z.w}
              height={z.h}
              rx={3.4}
              fill={colour ? `url(#apple-glow-${z.room.id})` : 'rgb(255 255 255 / 0.025)'}
              stroke={colour ? `${colour}66` : 'rgb(255 255 255 / 0.1)'}
              strokeWidth={0.35}
            />
            <text
              x={z.x + 2.6}
              y={z.labelAt === 'top' ? z.y + 5.4 : z.y + z.h - 2.6}
              fontSize={2.9}
              letterSpacing={0.35}
              fill={colour ?? '#7d7a8c'}
              opacity={0.85}
            >
              {z.room.name.toUpperCase()}
            </text>
          </g>
        )
      })}

      {links.map(([a, b]) => {
        const d = curve(a, b)
        const key = `${a.device.id}-${b.device.id}`
        return broken(a) || broken(b) ? (
          <path key={key} data-link="broken" d={d} fill="none" stroke="rgb(240 189 90 / 0.5)" strokeWidth={0.4} strokeDasharray=".8 1.6" />
        ) : (
          <g key={key} data-link="up">
            <path d={d} fill="none" stroke="rgb(180 169 255 / 0.2)" strokeWidth={0.45} />
            <path d={d} fill="none" stroke="#c3b9ff" strokeWidth={0.8} strokeLinecap="round" strokeDasharray="2 30" className="motion-safe:animate-thread" />
          </g>
        )
      })}

      {all.map((o) => {
        const p = o.room.playing
        const ripple = plays(o)
        const colour = ripple && p ? colourOf(p) : null
        const up = o.device.online
        return (
          <g key={o.device.id} data-device={o.device.id} data-online={up}>
            <title>{`${o.device.name}: ${up ? 'online' : 'offline'}`}</title>
            {colour &&
              [0, 1.8].map((delay) => (
                <circle
                  key={delay}
                  cx={o.x}
                  cy={o.y}
                  r={6}
                  fill="none"
                  stroke={colour}
                  strokeWidth={0.5}
                  className="origin-center [transform-box:fill-box] motion-safe:animate-ripple"
                  style={{ animationDelay: `${delay}s` }}
                />
              ))}
            <circle
              cx={o.x}
              cy={o.y}
              r={10}
              fill={`url(#${!up ? 'apple-halo-amber' : colour === VIDEO ? 'apple-halo-video' : colour ? 'apple-halo-music' : 'apple-orb'})`}
              opacity={up && !colour ? 0.5 : 1}
            />
            <circle
              cx={o.x}
              cy={o.y}
              r={5}
              fill="url(#apple-orb)"
              stroke={!up ? AMBER : (colour ?? 'rgb(255 255 255 / 0.3)')}
              strokeWidth={0.45}
              strokeDasharray={up ? undefined : '1.2 1'}
            />
            <g color={up ? '#f1eff7' : AMBER}>
              <Glyph o={o} />
            </g>
          </g>
        )
      })}
    </svg>
  )
}

function planLabel(rooms: Room[]): string {
  return rooms
    .map((r) => {
      const off = r.devices.filter((d) => !d.online).map((d) => d.name)
      return `${r.name}: ${r.devices.length} device${r.devices.length === 1 ? '' : 's'}${off.length ? `, ${off.join(' and ')} offline` : ''}`
    })
    .join('; ')
}

function NowPlaying({ room }: { room: Room & { playing: ApplePlaying } }) {
  const p = room.playing
  const colour = colourOf(p)
  const details = [p.state === 'paused' ? 'Paused' : null, p.subtitle, p.app, room.name].filter(Boolean).join(' · ')
  return (
    <li
      data-state={p.state}
      style={{ '--c': colour } as CSSProperties}
      className="grid grid-cols-[46px_minmax(0,1fr)_auto] items-center gap-3 rounded-[12px] border border-glass-line bg-glass bg-linear-to-r from-[color-mix(in_srgb,var(--c)_14%,transparent)] to-transparent to-70% px-3 py-2.5"
    >
      {p.artwork ? (
        <img src={`/api/apple/artwork/${room.id}`} alt="" className="size-[46px] rounded-[9px] border border-glass-line object-cover" />
      ) : (
        <span
          aria-hidden="true"
          className="size-[46px] rounded-[9px] border border-glass-line"
          style={{ background: `radial-gradient(70% 80% at 40% 35%, ${colour}, transparent 70%), linear-gradient(160deg, #2a2440, #121118)` }}
        />
      )}
      <span className="min-w-0">
        <span className="block truncate text-[14px] font-semibold">{p.title}</span>
        <span className="block truncate text-[12px] text-muted">{details}</span>
      </span>
      <span aria-hidden="true" className="flex h-4 items-end gap-0.5">
        {[0, -0.3, -0.6, -0.15].map((delay) => (
          <i
            key={delay}
            className={cn('block h-1 w-[3px] rounded-[2px] bg-(--c)', p.state === 'playing' ? 'motion-safe:animate-eq' : 'opacity-60')}
            style={{ animationDelay: `${delay}s` }}
          />
        ))}
      </span>
    </li>
  )
}

/**
 * The Home panel's Apple devices screen in the hub: the house as lit rooms,
 * each Apple TV and HomePod an orb, the Thread border routers as one network,
 * and what plays per room below.
 */
export function AppleCard({ data }: { data: AppleDevices | undefined }) {
  if (!data?.rooms.length) return null
  const devices = data.rooms.flatMap((r) => r.devices)
  const offline = devices.filter((d) => !d.online).length
  const routers = devices.filter((d) => d.thread !== null)
  const threadUp = routers.filter((d) => d.online && d.thread).length
  const playingRooms = data.rooms.filter((r) => r.playing?.state === 'playing')
  const nowPlaying = data.rooms.filter((r): r is Room & { playing: ApplePlaying } => r.playing !== null)

  let pill: ReactNode
  if (offline) pill = <Pill tone="warn">{offline} offline</Pill>
  else if (playingRooms.length === 1) pill = <Pill tone="accent">Playing in {playingRooms[0].name}</Pill>
  else if (playingRooms.length > 1) pill = <Pill tone="accent">Playing in {playingRooms.length} rooms</Pill>
  else pill = <Pill tone="up">All online</Pill>

  return (
    <Card title="Apple devices" actions={pill}>
      <Plan rooms={data.rooms} />
      <div className="mt-2 flex flex-wrap justify-between gap-2.5 text-[12px] text-muted">
        <span>
          <b className="font-medium text-fg">{devices.length - offline}</b> of {devices.length} online
        </span>
        {routers.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <i
              aria-hidden="true"
              className={cn(
                'size-[7px] rounded-full',
                threadUp === routers.length ? 'bg-[#b4a9ff] shadow-[0_0_8px_#b4a9ff]' : 'bg-[#f0bd5a] shadow-[0_0_8px_#f0bd5a]',
              )}
            />
            Thread · {threadUp} of {routers.length} border routers
          </span>
        )}
      </div>
      {nowPlaying.length > 0 && (
        <ul aria-label="Playing" className="mt-3 grid gap-2.5">
          {nowPlaying.map((r) => (
            <NowPlaying key={r.id} room={r} />
          ))}
        </ul>
      )}
      {data.stale && <StaleNote />}
    </Card>
  )
}
