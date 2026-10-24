import type { CSSProperties } from 'react'
import { formatUptime, siteKey } from '../../lib/sites'
import type { Site, Sites } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { Pill } from '../ui/Pill'
import { SiteRings } from './SiteRings'

const REFRESH_MS = 60_000

function since(iso: string, now: Date): string {
  const minutes = Math.max(1, Math.round((now.getTime() - new Date(iso).getTime()) / 60_000))
  return minutes < 60 ? `down for ${minutes} min` : `down for ${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

function Row({ site, index, now }: { site: Site; index: number; now: Date }) {
  let right = null
  if (site.up === false) right = <span className="font-semibold text-down">{site.down_since ? since(site.down_since, now) : 'down'}</span>
  else if (site.uptime_pct != null && site.uptime_pct < 100) right = <span className="text-warn">{formatUptime(site.uptime_pct)}</span>
  return (
    <li className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2.5 border-glass-line py-1.5 text-small not-first:border-t">
      <i aria-hidden="true" style={{ '--key': siteKey(site, index) } as CSSProperties} className="block h-1 w-2.5 rounded-[2px] bg-(--key)" />
      <span className="truncate">{site.name}</span>
      <span className="text-caption tabular-nums">{right}</span>
    </li>
  )
}

/**
 * The owner's websites on the Services page, the House panel's My sites card:
 * rings of 30 days per site and the sites in their Kuma groups.
 */
export function MySitesSection() {
  const { data, error } = useApi<Sites>('/api/sites', REFRESH_MS)
  const now = new Date()
  const sites = data?.sites ?? []
  const down = sites.filter((s) => s.up === false).length
  const groups = [...new Set(sites.map((s) => s.group))]

  return (
    <Card
      title="My sites"
      className="mt-5"
      actions={data && sites.length > 0 && (down ? <Pill tone="down">{down} down</Pill> : <Pill tone="up">All up</Pill>)}
    >
      {!data && (error ? <Unavailable what="My sites" /> : <Loading />)}
      {data && sites.length === 0 && <p className="text-muted">No sites on Kuma's status page yet.</p>}
      {sites.length > 0 && (
        <>
          <p className="-mt-2 mb-3 text-caption text-faint">From Uptime Kuma, 30 days, a segment per day.</p>
          <div className="grid items-center justify-items-center gap-4 md:grid-cols-[260px_minmax(0,1fr)] md:justify-items-stretch md:gap-7">
            <SiteRings sites={sites} />
            <div className="grid w-full gap-x-7 sm:grid-cols-2">
              {groups.map((group) => (
                <section key={group} aria-label={group}>
                  <h3 className="mt-0.5 mb-1 text-label font-semibold tracking-[0.08em] text-faint uppercase">{group}</h3>
                  <ul>
                    {sites.map((s, i) => [s, i] as const).filter(([s]) => s.group === group).map(([s, i]) => (
                      <Row key={s.id} site={s} index={i} now={now} />
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </div>
          {data?.stale && <StaleNote />}
        </>
      )}
    </Card>
  )
}
