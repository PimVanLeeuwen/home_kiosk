import { cn } from '../../lib/cn'
import { formatBytes, formatDuration } from '../../lib/format'
import type { MediaDownload } from '../../lib/types'
import { Poster } from './Poster'
import { Tag } from '../ui/Tag'

const CHIP: Partial<Record<MediaDownload['state'], string>> = {
  failed: 'Failed',
  warning: 'Needs a look',
  importing: 'Importing',
  paused: 'Paused',
  queued: 'Queued',
}

/** One download: poster, title, what it is, a progress bar with light running along it. */
export function DownloadTile({ item }: { item: MediaDownload }) {
  const bad = item.state === 'failed'
  const warn = item.state === 'warning'
  const running = item.state === 'downloading'
  return (
    <li
      data-state={item.state}
      className={cn(
        'grid grid-cols-[52px_minmax(0,1fr)_auto] items-center gap-3.5 rounded-tile border p-3',
        bad
          ? 'border-down/40 bg-linear-to-br from-down/11 to-down/2'
          : warn
            ? 'border-warn/35 bg-linear-to-br from-warn/10 to-warn/2'
            : 'border-glass-line bg-glass',
      )}
    >
      <Poster poster={item.poster} title={item.title} />
      <div className="min-w-0">
        <p className="truncate text-body font-medium">
          {item.title}
          {CHIP[item.state] && (
            <Tag variant={bad || warn ? 'outline' : 'glass'} tone={bad ? 'down' : 'warn'} className="ml-1.5 align-[1px]">
              {CHIP[item.state]}
            </Tag>
          )}
        </p>
        <p className="text-caption text-muted">{item.detail}</p>
        <p className="text-caption text-muted">
          {formatBytes(item.size_bytes)}
          {item.client && ` · ${item.client}`}
        </p>
        {item.message && <p className={cn('text-caption', bad ? 'text-down' : 'text-warn')}>{item.message}</p>}
        <div
          role="progressbar"
          aria-label={`${item.title} ${item.detail}`}
          aria-valuenow={Math.round(item.progress_pct)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="relative mt-2 h-1.5 overflow-hidden rounded-full bg-white/7"
        >
          <i
            style={{ width: `${item.progress_pct}%` }}
            className={cn(
              'absolute inset-y-0 left-0 block rounded-full',
              bad
                ? 'bg-down'
                : warn
                  ? 'bg-warn shadow-[0_0_10px_--alpha(var(--color-warn)/60%)]'
                  : 'bg-linear-to-r from-accent to-accent-fg shadow-[0_0_10px_--alpha(var(--color-accent-line)/70%)]',
            )}
          >
            {running && (
              <span className="absolute inset-y-0 w-[30%] bg-linear-to-r from-transparent via-white/35 to-transparent motion-safe:animate-flow" />
            )}
          </i>
        </div>
      </div>
      <div className="text-right">
        <b className="block text-heading font-semibold">{Math.round(item.progress_pct)}%</b>
        {item.time_left_seconds != null && running && (
          <span className="text-caption whitespace-nowrap text-muted">{formatDuration(item.time_left_seconds)} left</span>
        )}
      </div>
    </li>
  )
}
