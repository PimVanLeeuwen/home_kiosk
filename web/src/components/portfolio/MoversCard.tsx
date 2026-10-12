import { Link } from 'react-router'
import { cn } from '../../lib/cn'
import { formatSignedPct } from '../../lib/format'
import { holdingPath } from '../../lib/portfolio'
import type { HoldingRow } from '../../lib/portfolioTypes'
import { squarify, type Tile } from '../../lib/treemap'
import { Card } from '../home/Card'

/** On a phone, holdings below this weight share one "others" tile, so none is too thin to read. */
const PHONE_MIN_WEIGHT = 3
/** The layout boxes: wide from md up, and a phone's. Tiles are placed in percent of these. */
const WIDE = { w: 660, h: 230 }
const PHONE = { w: 320, h: 280 }

type Cell = { kind: 'holding'; h: HoldingRow } | { kind: 'others'; count: number; weight: number; move: number }

const weightOf = (c: Cell) => (c.kind === 'holding' ? c.h.weight_pct : c.weight)
const moveOf = (c: Cell) => (c.kind === 'holding' ? c.h.day_pct : c.move)

/** Green or red, stronger for a bigger move; a 3% move is as strong as it gets. */
function tint(move: number) {
  const rgb = move >= 0 ? '63 185 127' : '229 100 106'
  const a = 0.16 + Math.min(Math.abs(move) / 3, 1) * 0.5
  return {
    background: `linear-gradient(150deg, rgb(${rgb} / ${a.toFixed(2)}), rgb(${rgb} / ${(a * 0.45).toFixed(2)}))`,
    borderColor: `rgb(${rgb} / 0.35)`,
  }
}

function TileView({ tile, box }: { tile: Tile<Cell>; box: { w: number; h: number } }) {
  const c = tile.item
  const move = moveOf(c)
  // Big tiles stack ticker, change and name (about 80 px high); small ones show ticker and
  // change, on one line from about 110 px wide or on two from about 52 px high; the rest only
  // the ticker (the change is in the link's name for screen readers).
  const size =
    tile.w >= 90 && tile.h >= 80
      ? 'lg'
      : (tile.w >= 110 && tile.h >= 30) || (tile.w >= 62 && tile.h >= 52)
        ? 'sm'
        : 'xs'
  const style = {
    left: `calc(${(tile.x / box.w) * 100}% + 2px)`,
    top: `calc(${(tile.y / box.h) * 100}% + 2px)`,
    width: `calc(${(tile.w / box.w) * 100}% - 4px)`,
    height: `calc(${(tile.h / box.h) * 100}% - 4px)`,
    ...tint(move),
  }
  const words = `${move >= 0 ? 'up' : 'down'} ${formatSignedPct(Math.abs(move)).replace(/^[+−]/, '')} today`
  const body = (
    <>
      <span className="truncate font-mono text-[12.5px] font-semibold">
        {c.kind === 'holding' ? c.h.symbol : size === 'xs' ? `+${c.count}` : `${c.count} others`}
      </span>
      {size !== 'xs' && (
        <span className={cn('min-w-0', size === 'sm' && 'inline')}>
          <b className={cn('font-semibold', size === 'lg' ? 'block text-[15px]' : 'text-[12px]')}>{formatSignedPct(move)}</b>
          {size === 'lg' && c.kind === 'holding' && <small className="block truncate text-[11px] text-fg/75">{c.h.name}</small>}
        </span>
      )}
    </>
  )
  const className = cn(
    'absolute flex overflow-hidden rounded-[9px] border hover:brightness-125',
    size === 'lg' ? 'flex-col justify-between px-2.5 py-2' : 'flex-row flex-wrap content-start items-baseline gap-x-1.5 px-2 py-1.5',
  )
  return c.kind === 'holding' ? (
    <Link to={holdingPath(c.h)} aria-label={`${c.h.symbol}, ${words}`} className={className} style={style}>
      {body}
    </Link>
  ) : (
    <a href="#holdings" aria-label={`${c.count} smaller holdings, together ${words}`} className={className} style={style}>
      {body}
    </a>
  )
}

function HeatMap({ cells, box, className }: { cells: Cell[]; box: { w: number; h: number }; className: string }) {
  const tiles = squarify(cells, weightOf, box.w, box.h)
  return (
    <div className={cn('relative overflow-hidden rounded-[12px]', className)} style={{ aspectRatio: `${box.w} / ${box.h}` }}>
      {tiles.map((t) => (
        <TileView key={t.item.kind === 'holding' ? t.item.h.symbol : 'others'} tile={t} box={box} />
      ))}
    </div>
  )
}

/** Today's movers as a heat map, as on the Money panel: each holding sized by its weight and tinted by today's move. */
export function MoversCard({ holdings }: { holdings: HoldingRow[] }) {
  const sorted = [...holdings].filter((h) => h.weight_pct > 0).sort((a, b) => b.weight_pct - a.weight_pct)
  if (!sorted.length) return null
  const up = sorted.filter((h) => h.day_pct >= 0).length

  const all: Cell[] = sorted.map((h) => ({ kind: 'holding', h }))
  const big = sorted.filter((h) => h.weight_pct >= PHONE_MIN_WEIGHT)
  const small = sorted.filter((h) => h.weight_pct < PHONE_MIN_WEIGHT)
  const phone: Cell[] =
    small.length < 2
      ? all
      : [
          ...big.map((h): Cell => ({ kind: 'holding', h })),
          {
            kind: 'others',
            count: small.length,
            weight: small.reduce((s, h) => s + h.weight_pct, 0),
            // The others' move together, weighted by their size.
            move: small.reduce((s, h) => s + h.day_pct * h.weight_pct, 0) / small.reduce((s, h) => s + h.weight_pct, 0),
          },
        ]

  return (
    <Card
      title="Today's movers"
      actions={
        <span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">
          {up} up · {sorted.length - up} down
        </span>
      }
    >
      <HeatMap cells={all} box={WIDE} className="hidden md:block" />
      <HeatMap cells={phone} box={PHONE} className="md:hidden" />
    </Card>
  )
}
