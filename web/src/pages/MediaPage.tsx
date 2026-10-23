import type { ReactNode } from 'react'
import { Card } from '../components/ui/Card'
import { Loading, StaleNote, Unavailable } from '../components/ui/states'
import { DownloadTile } from '../components/media/DownloadTile'
import { RequestsCard } from '../components/media/RequestsCard'
import { LibraryCard, WatchingCard } from '../components/media/WatchingCard'
import { Poster } from '../components/media/Poster'
import { PageHeader } from '../components/PageHeader'
import { GlowDot } from '../components/ui/GlowDot'
import { Pill } from '../components/ui/Pill'
import { formatAgo, formatTime } from '../lib/format'
import { byDay, episodeCode } from '../lib/media'
import type { Media, MediaEpisode, MediaOverview } from '../lib/types'
import { useApi } from '../lib/useApi'

const NAMES: Record<string, string> = { sonarr: 'Sonarr', radarr: 'Radarr' }

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2.5 py-1.5 text-muted">
      <GlowDot tone="up" />
      {children}
    </p>
  )
}

function EpisodeRow({ episode, right }: { episode: MediaEpisode; right: ReactNode }) {
  return (
    <li className="grid grid-cols-[34px_minmax(0,1fr)_auto] items-center gap-3 border-glass-line py-2 not-first:border-t">
      <Poster poster={episode.poster} title={episode.series} small />
      <div className="min-w-0">
        <p className="truncate text-[13.5px] font-medium">
          {episode.series} <span className="font-normal text-muted">{episodeCode(episode)}</span>
        </p>
        {episode.title && <p className="truncate text-[12px] text-muted">{episode.title}</p>}
      </div>
      <span className="text-right text-[12px] whitespace-nowrap text-faint">{right}</span>
    </li>
  )
}

export function MediaPage() {
  const { data, error } = useApi<Media>('/api/media', 60_000)
  // Tracearr and Seerr; left out entirely when not set up (no Tracearr key).
  const { data: overview } = useApi<MediaOverview>('/api/media/overview', 300_000)
  const now = new Date()
  const needLook = data?.downloads.filter((d) => d.state === 'failed' || d.state === 'warning').length ?? 0

  return (
    <>
      <PageHeader
        title="Media"
        subtitle="What is downloading, missing and airing next"
        actions={
          data &&
          (needLook ? (
            <Pill tone="warn">
              {needLook} need{needLook === 1 ? 's' : ''} a look
            </Pill>
          ) : data.downloads.length ? (
            <Pill tone="accent">{data.downloads.length} downloading</Pill>
          ) : (
            <Pill tone="up">All quiet</Pill>
          ))
        }
      />

      {!data && (error ? <Unavailable what="Media" /> : <Loading />)}

      {data && (
        <>
          {Object.entries(data.errors).map(([source, reason]) => (
            <p key={source} role="status" className="-mt-3 mb-4 text-[12.5px] text-warn">
              {NAMES[source] ?? source} could not be read ({reason}); its part is missing below.
            </p>
          ))}

          <dl className="mb-5 flex flex-wrap gap-x-5 gap-y-2 md:gap-x-6">
            {(
              [
                ['downloading', data.downloads.length, false],
                ['missing', data.missing_total, data.missing_total > 0],
                ['airing this week', data.upcoming.length, false],
              ] as const
            ).map(([label, n, warn]) => (
              <div key={label} className="flex items-baseline gap-2">
                <dt className="order-2 text-[13px] text-muted md:text-[14px]">{label}</dt>
                <dd className={`m-0 text-[22px] font-semibold tracking-tight md:text-[28px] ${warn ? 'text-warn' : ''}`}>{n}</dd>
              </div>
            ))}
          </dl>

          <div className="grid items-start gap-3.5 md:gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className="grid gap-3.5 md:gap-5">
              <Card title="Downloading" actions={<span className="text-[12px] text-faint">Sonarr · Radarr</span>}>
                {data.downloads.length ? (
                  <ul className="space-y-2.5">
                    {data.downloads.map((d) => (
                      <DownloadTile key={d.id} item={d} />
                    ))}
                  </ul>
                ) : (
                  <Empty>Nothing downloading</Empty>
                )}
              </Card>
              {overview && <RequestsCard overview={overview} />}
            </div>

            <div className="grid gap-3.5 md:gap-5">
              <Card
                title="Missing"
                actions={data.missing_total > 0 && <Pill tone="warn">{data.missing_total} {data.missing_total === 1 ? 'episode' : 'episodes'}</Pill>}
              >
                {data.missing.length ? (
                  <ul>
                    {data.missing.map((e) => (
                      <EpisodeRow key={`${e.series}-${e.season}-${e.episode}`} episode={e} right={e.air_date ? `aired ${formatAgo(e.air_date, now)}` : ''} />
                    ))}
                  </ul>
                ) : (
                  <Empty>Nothing missing</Empty>
                )}
                {data.missing_total > data.missing.length && (
                  <p className="mt-2 text-[12px] text-faint">The newest {data.missing.length} of {data.missing_total}.</p>
                )}
              </Card>

              <Card title="Next to air" actions={<span className="text-[12px] text-faint">7 days</span>}>
                {data.upcoming.length ? (
                  byDay(data.upcoming, now).map(([day, episodes]) => (
                    <section key={day} aria-label={day} className="not-first:mt-3">
                      <h3 className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">{day}</h3>
                      <ul>
                        {episodes.map((e) => (
                          <EpisodeRow
                            key={`${e.series}-${e.season}-${e.episode}`}
                            episode={e}
                            right={e.episode === 1 ? 'premiere' : e.air_date ? formatTime(e.air_date) : ''}
                          />
                        ))}
                      </ul>
                    </section>
                  ))
                ) : (
                  <p className="text-muted">Nothing airs in the coming week.</p>
                )}
              </Card>
            </div>
          </div>
          {overview && (
            <div className="mt-3.5 grid items-start gap-3.5 md:mt-5 md:gap-5 lg:grid-cols-2">
              <WatchingCard overview={overview} />
              <LibraryCard overview={overview} />
            </div>
          )}
          {(data.stale || overview?.stale) && <StaleNote />}
        </>
      )}
    </>
  )
}
