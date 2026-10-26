import { useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { cn } from '../../lib/cn'
import { FILAMENT_KELVIN, whiteOf } from '../../lib/lightColour'
import { PIECE_LABEL, PLAN_WIDTH, WALL, planHeight, spots, type LightsPlan, type Piece, type Spot } from '../../lib/lightsPlan'
import type { LightGroup } from '../../lib/types'

/** What is being moved on the plan: a light by its id, or a piece of furniture by its place in the list. */
export type Placed = { light: string } | { piece: number }

interface Props {
  plan: LightsPlan
  groups: LightGroup[]
  /** The group whose lights are ringed. */
  selected?: string | null
  onSelect?: (groupId: string) => void
  /** Editing (Settings): lights and furniture can be dragged, or moved with the arrow keys. */
  onPlace?: (what: Placed, at: Spot) => void
  /** Editing: the piece of furniture last touched, outlined. */
  activePiece?: number | null
  className?: string
}

const STEP = 0.01 /* an arrow key's move, as a share of the room */
const clamp = (v: number) => Math.max(0, Math.min(1, v))

/**
 * The living room from above (plan.md M27, O): each light a pool in its own
 * white and brightness, breathing softly, the furniture as quiet outlines.
 * On the Lights page a tap selects a light's group; in Settings everything
 * can be moved.
 */
export function FloorPlan({ plan, groups, selected = null, onSelect, onPlace, activePiece = null, className }: Props) {
  const ids = useId()
  const svg = useRef<SVGSVGElement>(null)
  const [moving, setMoving] = useState<Placed | null>(null)
  const height = planHeight(plan.aspect)
  const inner = { w: PLAN_WIDTH - 2 * WALL, h: height - 2 * WALL }
  const px = (s: Spot) => ({ x: WALL + s.x * inner.w, y: WALL + s.y * inner.h })
  const where = spots(plan, groups)
  const editing = !!onPlace

  function share(e: PointerEvent): Spot | null {
    const matrix = svg.current?.getScreenCTM?.()
    if (!matrix) return null
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse())
    return { x: clamp((p.x - WALL) / inner.w), y: clamp((p.y - WALL) / inner.h) }
  }

  function grab(what: Placed, e: PointerEvent) {
    if (!onPlace) return
    e.preventDefault()
    svg.current?.setPointerCapture?.(e.pointerId)
    setMoving(what)
    onPlace(what, share(e) ?? at(what))
  }

  const at = (what: Placed): Spot => ('light' in what ? where[what.light] : plan.furniture[what.piece])

  function nudge(what: Placed, e: KeyboardEvent) {
    const moves: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
    const move = moves[e.key]
    if (!onPlace || !move) return
    e.preventDefault()
    const now = at(what)
    onPlace(what, { x: clamp(now.x + move[0] * STEP), y: clamp(now.y + move[1] * STEP) })
  }

  function press(groupId: string, e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect?.(groupId)
    }
  }

  const pieceBox = (p: Piece) => {
    const c = px(p)
    return { x: c.x - (p.w * inner.w) / 2, y: c.y - (p.h * inner.h) / 2, w: p.w * inner.w, h: p.h * inner.h }
  }

  return (
    <svg
      ref={svg}
      viewBox={`0 0 ${PLAN_WIDTH} ${height}`}
      role="group"
      aria-label="The living room from above, each light as a pool of its light"
      className={cn('block w-full touch-none select-none', className)}
      onPointerMove={(e) => {
        const s = moving && share(e)
        if (moving && s) onPlace?.(moving, s)
      }}
      onPointerUp={() => setMoving(null)}
      onPointerCancel={() => setMoving(null)}
    >
      <defs>
        <clipPath id={`${ids}room`}>
          <rect x={WALL} y={WALL} width={inner.w} height={inner.h} />
        </clipPath>
        <pattern id={`${ids}floor`} width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="#17171e" strokeWidth="1" />
        </pattern>
        {groups.flatMap((g) =>
          g.lights.map((l) => (
            <radialGradient key={l.id} id={`${ids}${l.id}`}>
              <stop offset="0" stopColor={whiteOf(l.kelvin ?? g.kelvin ?? FILAMENT_KELVIN)} stopOpacity="0.95" />
              <stop offset="0.38" stopColor={whiteOf(l.kelvin ?? g.kelvin ?? FILAMENT_KELVIN)} stopOpacity="0.4" />
              <stop offset="1" stopColor={whiteOf(l.kelvin ?? g.kelvin ?? FILAMENT_KELVIN)} stopOpacity="0" />
            </radialGradient>
          )),
        )}
      </defs>
      <rect width={PLAN_WIDTH} height={height} rx="18" fill="#0a0a0d" />
      <rect x={WALL} y={WALL} width={inner.w} height={inner.h} fill={`url(#${ids}floor)`} />

      {/* The pools: light adds up where two meet. */}
      <g style={{ mixBlendMode: 'screen' }} clipPath={`url(#${ids}room)`}>
        {groups.flatMap((g) =>
          g.lights
            .filter((l) => l.on && l.reachable)
            .map((l, i) => {
              const c = px(where[l.id])
              const r = 46 + l.brightness * 1.05
              return (
                <circle
                  key={l.id}
                  data-pool={l.id}
                  cx={c.x}
                  cy={c.y}
                  r={r}
                  fill={`url(#${ids}${l.id})`}
                  opacity={0.4 + (l.brightness / 100) * 0.6}
                  style={{ animationDelay: `${-i * 1.3}s`, transformBox: 'fill-box', transformOrigin: 'center' }}
                  className="motion-safe:animate-breathe"
                />
              )
            }),
        )}
      </g>

      <g fill="none" stroke="#3a3a46" strokeWidth="1.5">
        {plan.furniture.map((p, i) => {
          const b = pieceBox(p)
          return (
            <g
              key={`${p.kind}-${i}`}
              role={editing ? 'button' : undefined}
              tabIndex={editing ? 0 : undefined}
              aria-label={editing ? `${PIECE_LABEL[p.kind]}: drag or use the arrow keys to move it` : undefined}
              onPointerDown={(e) => grab({ piece: i }, e)}
              onKeyDown={(e) => nudge({ piece: i }, e)}
              className={cn(editing && 'cursor-grab outline-none')}
            >
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={p.kind === 'tv' ? 2 : p.kind === 'table' ? Math.min(b.w, b.h) / 2 : 10}
                stroke={editing && activePiece === i ? 'var(--color-accent)' : undefined}
                fill={editing ? 'rgb(255 255 255 / 0.02)' : 'none'}
              />
              <text
                x={b.x + b.w / 2}
                y={b.y + b.h / 2 + 4}
                textAnchor="middle"
                fill="#5d5d6c"
                stroke="none"
                fontSize="11"
                letterSpacing="1.5"
              >
                {PIECE_LABEL[p.kind].toUpperCase()}
              </text>
            </g>
          )
        })}
      </g>

      <rect x={WALL / 2} y={WALL / 2} width={PLAN_WIDTH - WALL} height={height - WALL} rx="12" fill="none" stroke="#2c2c36" strokeWidth={WALL / 2} />

      {groups.flatMap((g) =>
        g.lights.map((l) => {
          const c = px(where[l.id])
          const lit = l.on && l.reachable
          const state = !l.reachable ? 'not reachable' : l.on ? `on at ${l.brightness}%` : 'off'
          return (
            <g
              key={l.id}
              role="button"
              tabIndex={0}
              aria-label={editing ? `${l.name}: drag or use the arrow keys to move it` : `${g.name}, ${l.name}: ${state}`}
              aria-pressed={editing ? undefined : selected === g.id}
              onClick={() => !editing && onSelect?.(g.id)}
              onKeyDown={(e) => (editing ? nudge({ light: l.id }, e) : press(g.id, e))}
              onPointerDown={(e) => grab({ light: l.id }, e)}
              className={cn('outline-none', editing ? 'cursor-grab' : 'cursor-pointer')}
            >
              <title>{`${l.name} · ${state}`}</title>
              {/* A bigger target than the dot, for fingers. */}
              <circle cx={c.x} cy={c.y} r="18" fill="transparent" />
              <circle
                cx={c.x}
                cy={c.y}
                r={lit ? 6.5 : 5.5}
                fill={lit ? '#fff4de' : '#22212a'}
                stroke={lit ? 'none' : '#55525f'}
                strokeWidth="1.5"
                strokeDasharray={l.reachable ? undefined : '2 2'}
              />
              {(selected === g.id || (editing && moving && 'light' in moving && moving.light === l.id)) && (
                <circle cx={c.x} cy={c.y} r="13" fill="none" stroke="#fff" strokeWidth="2" />
              )}
            </g>
          )
        }),
      )}
    </svg>
  )
}
