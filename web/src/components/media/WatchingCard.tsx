import { formatBytes } from '../../lib/format'
import { monogram, tileColour } from '../../lib/monogram'
import type { MediaOverview } from '../../lib/types'
import { Card } from '../ui/Card'

const hours = new Intl.NumberFormat('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const count = new Intl.NumberFormat('nl-NL')
const h = (seconds: number) => hours.format(seconds / 3600)

/** Who watched how much in the last 30 days, from Tracearr; usernames only. */
export function WatchingCard({ overview }: { overview: MediaOverview }) {
  const viewers = overview.viewers
  const top = viewers?.[0]?.watch_seconds || 1
  return (
    <Card title="Watching · 30 days" actions={<span className="text-[12px] text-faint">Tracearr</span>}>
      {!viewers ? (
        <p className="text-muted">Tracearr could not be read{overview.errors.tracearr ? ` (${overview.errors.tracearr})` : ''}.</p>
      ) : (
        <>
          <dl className="mb-3.5 flex gap-6">
            <div className="flex items-baseline gap-1.5">
              <dt className="order-2 text-muted">hours</dt>
              <dd className="m-0 text-[26px] font-semibold tracking-tight">{h(viewers.reduce((s, v) => s + v.watch_seconds, 0))}</dd>
            </div>
            <div className="flex items-baseline gap-1.5">
              <dt className="order-2 text-muted">plays</dt>
              <dd className="m-0 text-[26px] font-semibold tracking-tight">{count.format(viewers.reduce((s, v) => s + v.plays, 0))}</dd>
            </div>
          </dl>
          {viewers.length ? (
            <ol aria-label="Leaderboard">
              {viewers.map((v, i) => {
                const colour = tileColour(i)
                return (
                  <li key={v.name} className="grid grid-cols-[18px_30px_minmax(0,1fr)_auto] items-center gap-2.5 py-1.5">
                    <span className="text-right text-[12px] text-faint tabular-nums">{i + 1}</span>
                    <span aria-hidden="true" style={{ backgroundColor: colour.bg, color: colour.fg, boxShadow: `0 0 12px -4px ${colour.fg}` }} className="grid size-[30px] place-items-center rounded-full text-[11.5px] font-bold">
                      {monogram(v.name)}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[13.5px]">{v.name}</p>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/7">
                        <i style={{ width: `${(v.watch_seconds / top) * 100}%` }} className="block h-full rounded-full bg-linear-to-r from-accent to-accent-fg shadow-[0_0_8px_rgb(143_128_255/0.6)]" />
                      </div>
                    </div>
                    <p className="text-right text-[13px] font-semibold">
                      {h(v.watch_seconds)} h<span className="block text-[11.5px] font-normal text-muted">{v.plays} plays</span>
                    </p>
                  </li>
                )
              })}
            </ol>
          ) : (
            <p className="text-muted">Nobody watched in the last 30 days.</p>
          )}
          {overview.idle_viewers > 0 && (
            <p className="mt-1.5 text-[12px] text-faint">
              {overview.idle_viewers} more without plays in 30 days.
            </p>
          )}
          {overview.genres.length > 0 && (
            <div className="mt-3">
              <p className="mb-1.5 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Most-watched genres, all time</p>
              <ul className="flex flex-wrap gap-1.5">
                {overview.genres.map((g) => (
                  <li key={g} className="rounded-full bg-accent/12 px-2.5 py-0.5 text-[11.5px] text-accent-fg">
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

/** The library's size from Tracearr, with what was added this week. */
export function LibraryCard({ overview }: { overview: MediaOverview }) {
  const lib = overview.library
  if (!lib) return null
  const tiles: [string, number, number | null][] = [
    ['movies', lib.movies, lib.added_movies],
    ['shows', lib.shows, null],
    ['episodes', lib.episodes, lib.added_episodes],
  ]
  return (
    <Card title="Library" actions={<span className="text-[12px] text-faint">{formatBytes(lib.size_bytes)}</span>}>
      <ul className="grid grid-cols-3 gap-2.5">
        {tiles.map(([label, n, added]) => (
          <li key={label} className="rounded-[12px] border border-glass-line bg-glass p-3">
            <b className="block text-[22px] font-semibold">{count.format(n)}</b>
            <span className="text-[12px] text-muted">{label}</span>
            {added != null && added > 0 && <span className="block text-[11.5px] text-up">+{count.format(added)} this week</span>}
          </li>
        ))}
      </ul>
    </Card>
  )
}
