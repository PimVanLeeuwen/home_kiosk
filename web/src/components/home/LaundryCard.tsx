import type { CSSProperties, ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { formatAgo, formatTime } from '../../lib/format'
import type { Laundry, Machine } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Pill } from '../ui/Pill'
import { Card, StaleNote } from './Card'

const R = 44
const C = 2 * Math.PI * R
const MACHINE_COLOUR = { washer: '#9c8ffb', dryer: '#5aa9ff' } as const
const STATE_COLOUR = { done: 'var(--color-up)', paused: 'var(--color-warn)', error: 'var(--color-down)' } as const

function ringColour(m: Machine): string {
  return m.state === 'done' || m.state === 'paused' || m.state === 'error' ? STATE_COLOUR[m.state] : MACHINE_COLOUR[m.kind]
}

/** How far the program is, 0 to 1; a finished machine's ring is full. */
function progress(m: Machine): number {
  if (m.state === 'done') return 1
  if (!m.total_minutes || m.remaining_minutes == null) return 0
  return Math.max(0, Math.min(1, 1 - m.remaining_minutes / m.total_minutes))
}

/** A machine as a porthole: a ring for the program, water turning in the glass door. */
function Porthole({ m }: { m: Machine }) {
  const colour = ringColour(m)
  const filled = progress(m)
  const turning = m.state === 'running'
  const water = m.state === 'running' || m.state === 'paused'
  let inside: ReactNode
  if (m.state === 'done') {
    inside = (
      <svg viewBox="0 0 24 24" className="w-[38%]" aria-hidden="true">
        <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="var(--color-up)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" style={{ filter: 'drop-shadow(0 0 4px var(--color-up))' }} />
      </svg>
    )
  } else if (m.state === 'error') {
    inside = <span className="text-[20px] text-down">{m.error}</span>
  } else if (m.state === 'idle') {
    inside = <span className="text-[12px] font-normal text-muted">Off</span>
  } else {
    inside = (
      <>
        {m.remaining_minutes}
        <small className="mt-0.5 text-[11px] font-normal text-muted">min</small>
      </>
    )
  }
  return (
    <div className="relative mb-2 aspect-square w-32 md:w-[150px]">
      <svg viewBox="0 0 100 100" className="block size-full" aria-hidden="true">
        <circle cx="50" cy="50" r={R} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="4" />
        {filled > 0 && (
          <circle
            cx="50"
            cy="50"
            r={R}
            fill="none"
            stroke={colour}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${(C * filled).toFixed(1)} ${C.toFixed(1)}`}
            transform="rotate(-90 50 50)"
            style={{ filter: `drop-shadow(0 0 3px ${colour})` }}
          />
        )}
      </svg>
      <div
        style={{ '--wc': MACHINE_COLOUR[m.kind] } as CSSProperties}
        className={cn(
          'absolute inset-[13%] grid place-items-center overflow-hidden rounded-full bg-[radial-gradient(circle_at_35%_30%,rgb(255_255_255/0.14),rgb(255_255_255/0.02)_60%),#0e0e14]',
          m.state === 'done'
            ? 'shadow-[inset_0_0_0_4px_rgb(63_185_127/0.35),0_0_32px_rgb(63_185_127/0.3)]'
            : m.state === 'paused'
              ? 'shadow-[inset_0_0_0_4px_rgb(224_162_59/0.35),0_0_28px_rgb(224_162_59/0.25)]'
              : m.state === 'error'
                ? 'shadow-[inset_0_0_0_4px_rgb(229_100_106/0.4),0_0_28px_rgb(229_100_106/0.3)]'
                : 'shadow-[inset_0_0_0_4px_rgb(255_255_255/0.08),inset_0_-12px_24px_rgb(0_0_0/0.5)]',
        )}
      >
        {water && (
          <i
            data-water
            style={{ top: `${45 + 30 * progress(m)}%` }}
            className={cn('absolute -left-1/2 block size-[200%] rounded-[42%] bg-[color-mix(in_srgb,var(--wc)_35%,transparent)]', turning && 'motion-safe:animate-drum')}
          />
        )}
        <span className="relative grid place-items-center text-[22px] leading-none font-semibold md:text-[26px]">{inside}</span>
      </div>
    </div>
  )
}

function lines(m: Machine): [string, ReactNode] {
  switch (m.state) {
    case 'done':
      return [m.done_at ? `Done at ${formatTime(m.done_at)}` : 'Done', <span className="text-up">Take it out</span>]
    case 'paused':
      return [m.program ?? '', <span className="text-warn">Paused</span>]
    case 'error':
      return [m.error?.startsWith('F') ? 'See the manual' : (m.program ?? ''), <span className="text-down">{m.error?.startsWith('F') ? `Error ${m.error}` : m.error}</span>]
    case 'running':
      return [
        m.program ?? '',
        <span style={{ color: MACHINE_COLOUR[m.kind] }}>{m.ready_at ? `Ready at ${formatTime(m.ready_at)}` : 'Running'}</span>,
      ]
    default:
      return ['', '']
  }
}

function headline(machines: Machine[]): ReactNode {
  if (machines.some((m) => m.state === 'error')) return <Pill tone="down">Needs a look</Pill>
  if (machines.some((m) => m.state === 'done')) return <Pill tone="up">Done</Pill>
  if (machines.some((m) => m.state === 'paused')) return <Pill tone="warn">Paused</Pill>
  const running = machines.filter((m) => m.state === 'running')
  if (running.length > 1) return <Pill tone="accent">Both running</Pill>
  return <Pill tone="accent">{running[0]?.kind === 'dryer' ? 'Dryer running' : 'Washer running'}</Pill>
}

/**
 * The washer and dryer on Home, the Home panel's laundry card: only while a
 * machine runs, is paused, has an error or is done (until its door opens).
 */
export function LaundryCard() {
  const { data } = useApi<Laundry>('/api/laundry', 60_000)
  if (!data?.showing) return null
  const now = new Date()

  return (
    <Card title="Laundry" actions={headline(data.machines)}>
      <ul className="grid grid-cols-2 gap-4.5">
        {data.machines.map((m) => {
          const [first, second] = lines(m)
          return (
            <li key={m.id} data-state={m.state} className={cn('grid content-start justify-items-center gap-0.5 text-center', m.state === 'idle' && 'opacity-45')}>
              <Porthole m={m} />
              <p className="text-[15px] font-semibold">{m.name}</p>
              {first && <p className="text-[12.5px] text-muted">{first}</p>}
              {second && <p className="text-[13px] font-semibold">{second}</p>}
            </li>
          )
        })}
      </ul>
      <p className="mt-3.5 text-center text-[12px] text-faint">Updated {formatAgo(data.as_of, now)} · ConnectLife</p>
      {data.stale && <StaleNote />}
    </Card>
  )
}
