import { headline, STATE_LABEL, STATE_TEXT, troubled } from '../../lib/outside'
import type { OutsideServices } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { BrandLogo } from './BrandLogo'
import { IncidentCard } from './IncidentCard'
import { ReadNotes } from './ReadNotes'

const REFRESH_MS = 60_000

/** The Services page's full view: every outside service with its state and a
 * link to its status page, then each open incident and running maintenance. */
export function OutsideServicesSection() {
  const { data, error } = useApi<OutsideServices>('/api/outside-services', REFRESH_MS)
  const services = data?.services ?? []
  const open = troubled(services)
  const maintenance = services.filter((s) => s.state === 'maintenance')

  return (
    <section
      aria-labelledby="group-outside"
      className="mt-5 rounded-[14px] border border-line-soft bg-card p-4 md:px-6 md:py-5"
    >
      <h2 id="group-outside" className="mb-1 text-[13px] font-semibold text-muted">
        Outside services
      </h2>
      <p className="mb-3.5 text-[12.5px] text-faint">
        What the house depends on, from their status pages. Only the parts the house uses count.
      </p>
      {!data && (
        <p role="status" className="text-muted">
          {error ? 'The status of outside services is not available right now.' : 'Loading…'}
        </p>
      )}
      {data && (
        <>
          <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
            {services.map((s) => (
              <li key={s.key}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`${s.name}: ${STATE_LABEL[s.state]}, open the status page`}
                  className="flex items-center gap-3 rounded-[11px] border border-line-soft bg-raised/50 px-3 py-2.5 hover:border-line"
                >
                  <BrandLogo service={s} size={32} halo={s.state === 'degraded' || s.state === 'outage'} dim={s.state === 'unknown'} />
                  <span className="min-w-0">
                    <span className="block font-medium">{s.name}</span>
                    <span className={`block text-[12.5px] ${STATE_TEXT[s.state]}`}>{STATE_LABEL[s.state]}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
          {(open.length > 0 || maintenance.length > 0) && (
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {[...open, ...maintenance].flatMap((s) =>
                (s.incidents.length > 0 ? s.incidents : [headline(s)]).map((incident) => (
                  <IncidentCard key={`${s.key}-${incident.title}`} service={s} incident={incident} />
                )),
              )}
            </div>
          )}
          <ReadNotes services={services} />
          {data.stale && <p className="mt-3 text-[12px] text-warn">Showing the last known status.</p>}
        </>
      )}
    </section>
  )
}
