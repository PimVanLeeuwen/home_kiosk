import { RefreshCw } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { ServiceTile } from '../components/ServiceTile'
import { uniqueMonograms } from '../lib/monogram'
import type { ServicesResponse } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useServiceLinks } from '../lib/useServiceLinks'

const REFRESH_MS = 30_000

export function ServicesPage() {
  const services = useApi<ServicesResponse>('/api/services', REFRESH_MS)
  const linkFor = useServiceLinks()

  const all = services.data?.groups.flatMap((g) => g.services) ?? []
  const running = all.filter((s) => s.status === 'up').length
  const labels = uniqueMonograms(all.map((s) => s.name))
  const position = new Map(all.map((s, i) => [s.id, i]))
  const statusKnown = !!services.data && !services.data.stale && !services.error

  return (
    <>
      <PageHeader
        title="Services"
        subtitle={
          services.data
            ? `${running} of ${all.length} running`
            : 'Every app on the NAS, with status and links'
        }
      />

      {services.loading && !services.data && (
        <p className="text-muted" role="status">
          Loading services…
        </p>
      )}

      {services.error && !services.data && (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-[14px] border border-line bg-card p-5"
        >
          <p className="font-medium">The hub API is not answering</p>
          <p className="text-muted">Service links and status need the collector on the NAS.</p>
          <button
            type="button"
            onClick={services.reload}
            className="inline-flex items-center gap-2 rounded-[9px] border border-line bg-raised px-3 py-2 font-medium hover:border-faint"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            Try again
          </button>
        </div>
      )}

      {services.data && !statusKnown && (
        <p role="status" className="mb-4 text-[13px] text-warn">
          Status may be out of date: the latest container check did not come through.
        </p>
      )}

      {services.data && (
        <div className="space-y-5">
          {services.data.groups.map((group) => (
            <section
              key={group.name}
              aria-labelledby={`group-${group.name}`}
              className="rounded-[14px] border border-line-soft bg-card p-4 md:px-6 md:py-5"
            >
              <h2 id={`group-${group.name}`} className="mb-3.5 text-[13px] font-semibold text-muted">
                {group.name}
              </h2>
              <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
                {group.services.map((service) => (
                  <li key={service.id}>
                    <ServiceTile
                      service={service}
                      href={linkFor(service)}
                      label={labels[position.get(service.id)!]}
                      index={position.get(service.id)!}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  )
}
