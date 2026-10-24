import { OutsideServicesSection } from '../components/outside/OutsideServicesSection'
import { PageHeader } from '../components/PageHeader'
import { OutOf, StatTile, StatTiles } from '../components/ui/StatTile'
import { MySitesSection } from '../components/sites/MySitesSection'
import { Pill } from '../components/ui/Pill'
import { cn } from '../lib/cn'
import { ServiceTile } from '../components/ServiceTile'
import { uniqueMonograms } from '../lib/monogram'
import type { Service, ServiceStatus, ServicesResponse } from '../lib/types'
import { useApi } from '../lib/useApi'
import { useServiceLinks } from '../lib/useServiceLinks'
import { PageUnavailable, StaleNote } from '../components/ui/states'
import { Surface } from '../components/ui/Card'

const REFRESH_MS = 30_000

/** The summary's dot per service: green up, amber starting or unhealthy, red down, grey for a link. */
const DOT: Record<ServiceStatus | 'link', string> = {
  up: 'bg-up shadow-[0_0_5px_--alpha(var(--color-up)/70%)]',
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
  if (!nas.length) return <span className="rounded-[6px] bg-raised px-1.5 text-micro text-muted">{services.length} links</span>
  const up = nas.filter((s) => s.status === 'up').length
  const tone = nas.some((s) => s.status === 'down' || s.status === 'missing') ? 'down' : up < nas.length ? 'warn' : 'up'
  return (
    <span
      data-tone={tone}
      className={cn(
        'rounded-[6px] px-1.5 text-micro',
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
  const troubled = onNas.filter((s) => ['down', 'missing', 'unhealthy'].includes(s.status))
  const needLook = troubled.length

  return (
    <>
      <PageHeader
        title="Services"
        subtitle={
          services.data
            ? `${running} of ${onNas.length} running`
            : 'Every app on the NAS, with status and links'
        }
        status={
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
        <PageUnavailable what="The hub API" detail="Service links and status need the collector on the NAS." onRetry={services.reload} />
      )}

      {services.data && !statusKnown && (
        <StaleNote banner>Status may be out of date: the latest container check did not come through.</StaleNote>
      )}

      {services.data && onNas.length > 0 && (
        <StatTiles label="Summary" count={3}>
          <StatTile title="Running" figure={<OutOf n={running} of={onNas.length} />}>
            <p className="mt-2.5 flex flex-wrap gap-1.5" aria-hidden="true">
              {all.map((s) => (
                <i key={s.id} title={s.name} data-status={s.url ? 'link' : s.status} className={cn('block size-[9px] rounded-full', DOT[s.url ? 'link' : s.status])} />
              ))}
            </p>
          </StatTile>
          <StatTile
            title="Needs a look"
            figure={needLook}
            tone={needLook ? 'warn' : undefined}
            sub={needLook ? troubled.map((s) => s.name).join(', ') : 'Nothing stopped or unhealthy'}
          />
          <StatTile title="Links" figure={all.length - onNas.length} sub="outside the NAS" />
        </StatTiles>
      )}

      {services.data && (
        <div className="space-y-5">
          {services.data.groups.map((group) => (
            <Surface as="section" key={group.name} aria-labelledby={`group-${group.name}`}>
              <div className="mb-3.5 flex items-center gap-2">
                <h2 id={`group-${group.name}`} className="text-small font-semibold text-muted">
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
            </Surface>
          ))}
        </div>
      )}

      <MySitesSection />
      <OutsideServicesSection />
    </>
  )
}
