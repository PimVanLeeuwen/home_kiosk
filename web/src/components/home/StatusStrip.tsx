import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'
import type { Chip, ChipTone, Segment } from '../../lib/homeChips'
import type { FoldedCardId } from '../../lib/homeOrder'
import { GlowDot } from '../ui/GlowDot'

const DOT_TONE = { ok: 'up', warn: 'warn', down: 'down', unknown: 'muted' } as const

/** Glass while all is well; something that needs a look tints its chip. */
const SURFACE: Record<ChipTone, string> = {
  ok: 'border-white/[0.075] from-white/[0.055] to-white/[0.012]',
  unknown: 'border-white/[0.075] from-white/[0.055] to-white/[0.012]',
  warn: 'border-warn/40 from-warn/15 to-warn/[0.03]',
  down: 'border-down/45 from-down/20 to-down/[0.03]',
}

const SEGMENT: Record<Segment, string> = {
  up: 'bg-up/75',
  accent: 'bg-accent-line/80',
  warn: 'bg-warn/80',
  down: 'bg-down shadow-[0_0_6px_var(--color-down)]',
  off: 'bg-white/[0.08]',
}

/** The id of the card a chip opens below the strip. */
export const OPENED_ID = 'home-opened-card'

function Meter({ segments }: { segments: Segment[] }) {
  if (!segments.length) return null
  return (
    <span aria-hidden="true" className="col-span-full mt-1.5 flex h-[3px] gap-[2px]">
      {segments.map((s, i) => (
        <i key={i} className={cn('flex-1 rounded-[2px]', SEGMENT[s])} />
      ))}
    </span>
  )
}

interface Props {
  chips: Chip[]
  /** Folded cards: their chip opens them. The others are on the page already. */
  folded: FoldedCardId[]
  open: FoldedCardId | null
  onToggle: (id: FoldedCardId) => void
  /** Brings a card that unfolded itself into view. */
  onShow: (id: FoldedCardId) => void
}

/**
 * The status strip on Home: one chip per house card with a small meter. While
 * all is well the card is folded into its chip, and the chip opens it.
 */
export function StatusStrip({ chips, folded, open, onToggle, onShow }: Props) {
  return (
    <div className="mb-5 grid grid-cols-2 gap-2.5 md:gap-3 xl:grid-cols-[repeat(4,minmax(0,1fr))_minmax(0,1.25fr)]">
      {chips.map((chip) => {
        const needsLook = chip.tone === 'warn' || chip.tone === 'down'
        const body = (
          <>
            <GlowDot tone={DOT_TONE[chip.tone]} halo={needsLook} />
            <span className="min-w-0">
              <span className="block text-[12px] text-muted">{chip.label}</span>
              <span className="block truncate text-[15px] font-semibold">{chip.value}</span>
            </span>
          </>
        )
        const surface = cn(
          'grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 rounded-[14px] border bg-card bg-linear-to-br px-3.5 py-3 text-left backdrop-blur-md md:px-4',
          SURFACE[chip.tone],
        )
        if (chip.id === 'alerts')
          return (
            <div key={chip.id} data-tone={chip.tone} className={cn(surface, 'col-span-2 xl:col-span-1')}>
              {body}
              <Meter segments={chip.meter} />
            </div>
          )
        const id = chip.id
        const isFolded = folded.includes(id)
        const expanded = isFolded && open === id
        return (
          <button
            key={id}
            type="button"
            data-tone={chip.tone}
            aria-expanded={isFolded ? expanded : undefined}
            aria-controls={expanded ? OPENED_ID : undefined}
            aria-label={`${chip.label}: ${chip.value}. ${isFolded ? (expanded ? 'Hide' : 'Show') : 'Go to'} the card`}
            onClick={() => (isFolded ? onToggle(id) : onShow(id))}
            className={cn(
              surface,
              'cursor-pointer transition-[border-color,transform] duration-200 hover:-translate-y-px hover:border-white/15 motion-reduce:transition-none motion-reduce:hover:translate-y-0',
              expanded && 'border-accent from-accent/25 to-accent/[0.05] hover:border-accent',
            )}
          >
            {body}
            <ChevronDown
              aria-hidden="true"
              className={cn('size-3.5 text-faint transition-transform duration-200', expanded && 'rotate-180 text-accent-fg')}
            />
            <Meter segments={chip.meter} />
          </button>
        )
      })}
    </div>
  )
}
