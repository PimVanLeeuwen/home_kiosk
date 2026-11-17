import { cn } from '../../lib/cn'
import type { MediaOverview, RequestState } from '../../lib/types'
import { Card } from '../ui/Card'
import { Poster } from './Poster'
import { Tag } from '../ui/Tag'
import type { Tone } from '../ui/tones'

const STATE: Record<RequestState, { label: string; tone: Tone }> = {
  waiting: { label: 'Waiting', tone: 'warn' },
  approved: { label: 'Approved', tone: 'muted' },
  downloading: { label: 'Downloading', tone: 'accent' },
  partly: { label: 'Partly available', tone: 'up' },
  available: { label: 'Available', tone: 'up' },
  declined: { label: 'Declined', tone: 'muted' },
  failed: { label: 'Failed', tone: 'down' },
}

function Count({ n, label, warn }: { n: number; label: string; warn?: boolean }) {
  return (
    <div className={cn('min-w-0 rounded-control border bg-glass px-3 py-2', warn && n > 0 ? 'border-warn/35' : 'border-glass-line')}>
      <b className={cn('block text-heading font-semibold', warn && n > 0 && 'text-warn')}>{n}</b>
      <span className="text-label text-muted">{label}</span>
    </div>
  )
}

/** Seerr's requests: how many wait or are being fetched, and the latest with where each stands. Read-only. */
export function RequestsCard({ overview }: { overview: MediaOverview }) {
  const counts = overview.requests
  return (
    <Card title="Requests" note="Seerr">
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
                    <p className="truncate text-small font-medium">{r.title}</p>
                    <p className="truncate text-caption text-muted">
                      {r.kind === 'movie' ? 'Movie' : 'Series'}
                      {r.year && ` · ${r.year}`} · {r.by}
                    </p>
                  </div>
                  <Tag variant="outline" tone={STATE[r.state].tone} data-state={r.state}>
                    {STATE[r.state].label}
                  </Tag>
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
