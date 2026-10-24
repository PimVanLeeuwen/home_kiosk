import type { CSSProperties } from 'react'
import { cn } from '../../lib/cn'
import { MAP_CENTRE, MAP_H, MAP_W, mapLine, mapPositions, PEER_TILE, SELF_TILE } from '../../lib/tailnet'
import type { TailnetDevice } from '../../lib/types'
import { DeviceIcon } from './DeviceIcon'

/** More than this and the names crowd; the list below still shows every device. */
const MAX_ON_MAP = 12

const LINE: Record<'direct' | 'relay', string> = {
  direct: 'var(--color-up)',
  relay: 'var(--color-accent-line)',
}

interface Props {
  peers: TailnetDevice[]
  /** A health warning turns the NAS amber. */
  warn: boolean
}

/**
 * The NAS in the middle and every device around it, as on the House panel: a
 * glowing line with light running along it for a direct connection, a dashed
 * violet one through a relay, a still grey one for an idle device, and a faint
 * dotted one to a device that is offline.
 */
export function TailnetMap({ peers, warn }: Props) {
  const shown = peers.slice(0, MAX_ON_MAP)
  const at = mapPositions(shown.length)
  const nas = warn ? 'var(--color-warn)' : 'var(--color-accent-line)'

  return (
    <figure
      aria-label={`The NAS and ${shown.length} ${shown.length === 1 ? 'device' : 'devices'}`}
      className="relative mx-auto my-0 aspect-[1.55] w-full max-w-[500px] @container"
    >
      <svg viewBox={`0 0 ${MAP_W} ${MAP_H}`} aria-hidden="true" className="absolute inset-0 size-full overflow-visible">
        {shown.map((p, i) => {
          const line = mapLine(at[i])
          const kind = !p.online ? 'offline' : (p.connection ?? 'idle')
          if (kind === 'direct' || kind === 'relay') {
            return (
              <g key={p.dns_name} data-line={kind} stroke={LINE[kind]} strokeLinecap="round">
                <line {...line} strokeOpacity={0.3} strokeWidth={0.6} strokeDasharray={kind === 'relay' ? '2 2' : undefined} />
                <line
                  {...line}
                  strokeWidth={1}
                  strokeDasharray="2 6"
                  className="motion-safe:animate-dash"
                  style={{ filter: `drop-shadow(0 0 1.2px ${LINE[kind]})` }}
                />
              </g>
            )
          }
          return (
            <line
              key={p.dns_name}
              data-line={kind}
              {...line}
              stroke="rgb(255 255 255 / 0.14)"
              strokeWidth={kind === 'idle' ? 0.8 : 0.5}
              strokeDasharray={kind === 'idle' ? undefined : '1.2 2.4'}
            />
          )
        })}
      </svg>

      {shown.map((p, i) => {
        // Names on the outside: above a device in the top half, below it otherwise.
        const above = at[i].y < MAP_CENTRE.y
        const name = (
          <span className={cn('text-caption whitespace-nowrap', p.online ? 'text-muted' : 'text-faint')}>
            {p.name}
            {!p.online && <span className="sr-only">, offline</span>}
          </span>
        )
        const glow = p.online && p.connection !== 'idle' ? LINE[p.connection === 'relay' ? 'relay' : 'direct'] : undefined
        return (
          <div
            key={p.dns_name}
            className="absolute grid justify-items-center gap-1"
            style={{
              left: `${at[i].x}%`,
              top: `${at[i].y}%`,
              transform: above ? `translate(-50%, calc(-100% + ${PEER_TILE * 50}cqw))` : 'translate(-50%, -50%)',
            }}
          >
            {above && name}
            <span
              style={{ width: `${PEER_TILE * 100}cqw`, height: `${PEER_TILE * 100}cqw`, '--glow': glow } as CSSProperties}
              className={cn(
                'relative grid place-items-center rounded-[30%] border bg-card',
                p.online
                  ? 'border-white/15 text-fg shadow-[0_0_16px_-4px_var(--glow,transparent)]'
                  : 'border-dashed border-white/20 text-faint opacity-50',
              )}
            >
              <DeviceIcon device={p} className="size-[45%]" />
              {p.exit_node && (
                <b
                  className={cn(
                    'absolute -right-3 rounded-full bg-accent px-1.5 text-micro font-semibold text-white',
                    // Away from the name: below the tile when the name is above it.
                    above ? '-bottom-2' : '-top-2',
                  )}
                >
                  EXIT
                </b>
              )}
            </span>
            {!above && name}
          </div>
        )
      })}

      <span
        style={
          {
            left: `${MAP_CENTRE.x}%`,
            top: `${MAP_CENTRE.y}%`,
            width: `${SELF_TILE * 100}cqw`,
            height: `${SELF_TILE * 100}cqw`,
            '--glow': nas,
          } as CSSProperties
        }
        className="absolute grid -translate-x-1/2 -translate-y-1/2 place-items-center rounded-[30%] border border-white/15 bg-card text-[clamp(13px,4.6cqw,22px)] font-bold shadow-[0_0_22px_-4px_var(--glow)]"
        data-warn={warn}
      >
        <span className="sr-only">This </span>NAS
      </span>
    </figure>
  )
}
