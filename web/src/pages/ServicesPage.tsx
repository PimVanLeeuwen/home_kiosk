import { RefreshCw } from 'lucide-react'
import { OutsideServicesSection } from '../components/outside/OutsideServicesSection'
import { PageHeader } from '../components/PageHeader'
import { Pill } from '../components/ui/Pill'
import { cn } from '../lib/cn'
import { ServiceTile } from '../components/ServiceTile'
import { uniqueMonograms } from '../lib/monogram'
import type { Service, ServiceStatus, ServicesResponse } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useServiceLinks } from '../lib/useServiceLinks'

const REFRESH_MS = 30_000

/** The summary's dot per service: green up, amber starting or unhealthy, red down, grey for a link. */
const DOT: Record<ServiceStatus | 'link', string> = {
  up: 'bg-up shadow-[0_0_5px_rgb(63_185_127/0.7)]',
  starting: 'bg-warn shadow-[0_0_7px_var(--color-warn)]',
  unhealthy: 'bg-warn shadow-[0_0_7px_var(--color-warn)]',
  down: 'bg-down shadow-[0_0_7px_var(--color-down)]',
  missing: 'bg-down shadow-[0_0_7px_var(--color-down)]',
  unknown: 'bg-faint',
  link: 'bg-white/14',
}

/** "3/4" running in a group, tinted by its worst service; "2 links" for a group of links. */
function GroupCount({ services }: { services: Service[] }) {
  const nas = services.filter((s) => !s.url)
  if (!nas.length) return <span className="rounded-[6px] bg-raised px-1.5 text-[10.5px] text-muted">{services.length} links</span>
  const up = nas.filter((s) => s.status === 'up').length
  const tone = nas.some((s) => s.status === 'down' || s.status === 'missing') ? 'down' : up < nas.length ? 'warn' : 'up'
  return (
    <span
      data-tone={tone}
      className={cn(
        'rounded-[6px] px-1.5 text-[10.5px]',
        tone === 'up' ? 'bg-up/13 text-up' : tone === 'down' ? 'bg-down/14 text-down' : 'bg-warn/15 text-warn',
      )}
    >
      {up}/{nas.length}
    </span>
  )
}

export function ServicesPage() {
  const services = useApi<ServicesResponse>('/api/services', REFRESH_MS)
  const linkFor = useServiceLinks()

  const all = services.data?.groups.flatMap((g) => g.services) ?? []
  // Links have no status; count NAS services only.
  const onNas = all.filter((s) => !s.url)
  const running = onNas.filter((s) => s.status === 'up').length
  const labels = uniqueMonograms(all.map((s) => s.name))
  const position = new Map(all.map((s, i) => [s.id, i]))
  const statusKnown = !!services.data && !services.data.stale && !services.error
  const needLook = onNas.filter((s) => ['down', 'missing', 'unhealthy'].includes(s.status)).length

  return (
    <>
      <PageHeader
        title="Services"
        subtitle={
          services.data
            ? `${running} of ${onNas.length} running`
            : 'Every app on the NAS, with status and links'
        }
        actions={
          services.data &&
          (needLook ? <Pill tone="warn">{needLook} need{needLook === 1 ? 's' : ''} a look</Pill> : <Pill tone="up">All running</Pill>)
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

      {services.data && onNas.length > 0 && (
        <section aria-label="Running" className="mb-5 rounded-[14px] border border-line-soft bg-card bg-linear-to-b from-white/[0.022] to-transparent px-5 py-4 md:px-6">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <p className="text-[30px] font-semibold tracking-tight">
              {running} <span className="text-[0.5em] font-medium text-muted">/ {onNas.length} running</span>
            </p>
            <p className="flex flex-wrap gap-1.5" aria-hidden="true">
              {all.map((s) => (
                <i key={s.id} title={s.name} data-status={s.url ? 'link' : s.status} className={cn('block size-[9px] rounded-full', DOT[s.url ? 'link' : s.status])} />
              ))}
            </p>
          </div>
        </section>
      )}

      {services.data && (
        <div className="space-y-5">
          {services.data.groups.map((group) => (
            <section
              key={group.name}
              aria-labelledby={`group-${group.name}`}
              className="rounded-[14px] border border-line-soft bg-card p-4 md:px-6 md:py-5"
            >
              <div className="mb-3.5 flex items-center gap-2">
                <h2 id={`group-${group.name}`} className="text-[13px] font-semibold text-muted">
                  {group.name}
                </h2>
                <GroupCount services={group.services} />
              </div>
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

      <OutsideServicesSection />
    </>
  )
}
