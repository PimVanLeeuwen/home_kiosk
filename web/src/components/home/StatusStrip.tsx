import { ChevronDown, ChevronRight } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import type { Chip, ChipTone, Segment } from '../../lib/homeChips'
import type { FoldedCardId } from '../../lib/homeOrder'
import { GlowDot } from '../ui/GlowDot'
import { PATHS } from '../../lib/paths'

/** Glass while all is well; something that needs a look tints its chip. */
const SURFACE: Record<ChipTone, string> = {
  up: 'border-white/[0.075] from-white/[0.055] to-white/[0.012]',
  muted: 'border-white/[0.075] from-white/[0.055] to-white/[0.012]',
  warn: 'border-warn/40 from-warn/15 to-warn/[0.03]',
  down: 'border-down/45 from-down/20 to-down/[0.03]',
}

const SEGMENT: Record<Segment, string> = {
  up: 'bg-up/75',
  accent: 'bg-accent-line/80',
  warn: 'bg-warn/80',
  down: 'bg-down shadow-glow shadow-down',
  off: 'bg-track',
}

/** The id of the card a chip opens below the strip. */
export const OPENED_ID = 'home-opened-card'

/** A chip's small bar of segments: a pool's fill, the services, the nights. */
function SegmentBar({ segments }: { segments: Segment[] }) {
  // Without segments the space stays, so every chip in a row has the same shape.
  if (!segments.length) return <span aria-hidden="true" className="col-span-full mt-1.5 h-[3px]" />
  return (
    <span aria-hidden="true" className="col-span-full mt-1.5 flex h-[3px] gap-[2px]">
      {segments.map((s, i) => (
        <i key={i} className={cn('flex-1 rounded-mark', SEGMENT[s])} />
      ))}
    </span>
  )
}

interface Props {
  chips: Chip[]
  /** Folded cards: their chip opens them. The others are on the page already. */
  folded: FoldedCardId[]
  open: FoldedCardId | null
  /** The page's first reveal: the chips rise one after another. */
  reveal?: boolean
  onToggle: (id: FoldedCardId) => void
  /** Brings a card that unfolded itself into view. */
  onShow: (id: FoldedCardId) => void
}

/**
 * The status strip on Home: one chip per house card with a small meter. While
 * all is well the card is folded into its chip, and the chip opens it.
 */
export function StatusStrip({ chips, folded, open, reveal, onToggle, onShow }: Props) {
  return (
    <div className="mb-5 grid grid-cols-2 gap-2.5 md:grid-cols-3 md:gap-3 2xl:grid-cols-[repeat(5,minmax(0,1fr))_minmax(0,1.25fr)]">
      {chips.map((chip, i) => {
        const needsLook = chip.tone === 'warn' || chip.tone === 'down'
        const body = (
          <>
            <GlowDot tone={chip.tone} halo={needsLook} />
            <span className="min-w-0">
              <span className="block text-small text-muted">{chip.label}</span>
              <span className="block truncate text-title font-semibold">{chip.value}</span>
            </span>
          </>
        )
        const surface = cn(
          'grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 rounded-card border bg-card bg-linear-to-br px-3.5 py-3 text-left backdrop-blur-md md:px-4',
          SURFACE[chip.tone],
          reveal && 'motion-safe:animate-rise',
        )
        const delay = reveal ? { animationDelay: `${(i + 1) * 55}ms` } : undefined
        const hover =
          'cursor-pointer transition-[border-color,transform] duration-200 hover:-translate-y-px hover:border-white/15 motion-reduce:transition-none motion-reduce:hover:translate-y-0'
        // Alerts has no card on Home: its chip goes to the Alerts page instead.
        if (chip.id === 'alerts')
          return (
            <Link
              key={chip.id}
              to={PATHS.alerts}
              data-tone={chip.tone}
              style={delay}
              aria-label={`${chip.label}: ${chip.value}. Go to Alerts`}
              className={cn(surface, hover)}
            >
              {body}
              <ChevronRight aria-hidden="true" className="size-3.5 text-faint" />
              <SegmentBar segments={chip.meter} />
            </Link>
          )
        const id = chip.id
        const isFolded = folded.includes(id)
        const expanded = isFolded && open === id
        return (
          <button
            key={id}
            type="button"
            data-tone={chip.tone}
            style={delay}
            aria-expanded={isFolded ? expanded : undefined}
            aria-controls={expanded ? OPENED_ID : undefined}
            aria-label={`${chip.label}: ${chip.value}. ${isFolded ? (expanded ? 'Hide' : 'Show') : 'Go to'} the card`}
            onClick={() => (isFolded ? onToggle(id) : onShow(id))}
            className={cn(
              surface,
              hover,
              expanded && 'border-accent from-accent/25 to-accent/[0.05] hover:border-accent',
            )}
          >
            {body}
            <ChevronDown
              aria-hidden="true"
              className={cn('size-3.5 text-faint transition-transform duration-200', expanded && 'rotate-180 text-accent-fg')}
            />
            <SegmentBar segments={chip.meter} />
          </button>
        )
      })}
    </div>
  )
}
