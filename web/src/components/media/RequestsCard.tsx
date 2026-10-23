import { cn } from '../../lib/cn'
import type { MediaOverview, RequestState } from '../../lib/types'
import { Card } from '../ui/Card'
import { Poster } from './Poster'

const STATE: Record<RequestState, { label: string; tone: string }> = {
  waiting: { label: 'Waiting', tone: 'border-warn/35 text-warn' },
  approved: { label: 'Approved', tone: 'border-glass-line text-muted' },
  downloading: { label: 'Downloading', tone: 'border-accent-line/30 text-accent-fg' },
  partly: { label: 'Partly available', tone: 'border-up/30 text-up' },
  available: { label: 'Available', tone: 'border-up/30 text-up' },
  declined: { label: 'Declined', tone: 'border-glass-line text-faint' },
  failed: { label: 'Failed', tone: 'border-down/40 text-down' },
}

function Count({ n, label, warn }: { n: number; label: string; warn?: boolean }) {
  return (
    <div className={cn('min-w-0 rounded-[10px] border bg-glass px-3 py-2', warn && n > 0 ? 'border-warn/35' : 'border-glass-line')}>
      <b className={cn('block text-[20px] font-semibold', warn && n > 0 && 'text-warn')}>{n}</b>
      <span className="text-[11.5px] text-muted">{label}</span>
    </div>
  )
}

/** Seerr's requests: how many wait or are being fetched, and the latest with where each stands. Read-only. */
export function RequestsCard({ overview }: { overview: MediaOverview }) {
  const counts = overview.requests
  return (
    <Card title="Requests" actions={<span className="text-[12px] text-faint">Seerr</span>}>
      {!counts ? (
        <p className="text-muted">Seerr could not be read{overview.errors.jellyseerr ? ` (${overview.errors.jellyseerr})` : ''}.</p>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-3 gap-2">
            <Count n={counts.pending} label="waiting for approval" warn />
            <Count n={counts.processing} label="being fetched" />
            <Count n={counts.completed} label="done, all time" />
          </div>
          {overview.latest_requests.length ? (
            <ul>
              {overview.latest_requests.map((r, i) => (
                <li key={`${r.title}-${i}`} className="grid grid-cols-[34px_minmax(0,1fr)_auto] items-center gap-3 border-glass-line py-2 not-first:border-t">
                  <Poster poster={r.poster} title={r.title} small />
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-medium">{r.title}</p>
                    <p className="truncate text-[12px] text-muted">
                      {r.kind === 'movie' ? 'Movie' : 'Series'}
                      {r.year && ` · ${r.year}`} · {r.by}
                    </p>
                  </div>
                  <span data-state={r.state} className={cn('rounded-[6px] border px-[7px] text-[11px] whitespace-nowrap', STATE[r.state].tone)}>
                    {STATE[r.state].label}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">No requests yet.</p>
          )}
        </>
      )}
    </Card>
  )
}
