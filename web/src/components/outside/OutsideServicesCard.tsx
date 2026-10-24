import { headline, STATE_LABEL, troubled } from '../../lib/outside'
import type { OutsideService, OutsideServices } from '../../lib/types'
import { Card } from '../ui/Card'
import { Loading, StaleNote, Unavailable } from '../ui/states'
import { BrandLogo } from './BrandLogo'
import { IncidentCard } from './IncidentCard'
import { ReadNotes } from './ReadNotes'

/** All well: the services as a ring around a glowing check. */
function Constellation({ services }: { services: OutsideService[] }) {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[230px]">
      <div
        aria-hidden="true"
        className="absolute inset-[18%] rounded-full bg-[radial-gradient(circle,--alpha(var(--color-up)/16%),transparent_70%)]"
      />
      <svg aria-hidden="true" viewBox="0 0 60 60" className="absolute inset-[32%]">
        <circle cx="30" cy="30" r="22" fill="color-mix(in srgb, var(--color-up) 14%, transparent)" stroke="color-mix(in srgb, var(--color-up) 45%, transparent)" strokeWidth="1.5" />
        <path d="M21 30.5l6 6 12-13" fill="none" stroke="var(--color-up)" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <ul>
        {services.map((s, i) => {
          const angle = (i / services.length) * 2 * Math.PI - Math.PI / 2
          return (
            <li
              key={s.key}
              title={`${s.name}: ${STATE_LABEL[s.state]}`}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${50 + 41 * Math.cos(angle)}%`, top: `${50 + 41 * Math.sin(angle)}%` }}
            >
              <BrandLogo service={s} size={38} dim={s.state === 'unknown'} />
              <span className="sr-only">
                {s.name}: {STATE_LABEL[s.state]}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** The outside services the house depends on, for a glance on Home. */
export function OutsideServicesCard({ data, error }: { data: OutsideServices | undefined; error: Error | undefined }) {
  const services = data?.services ?? []
  const problems = troubled(services)
  const fine = services.filter((s) => s.state === 'ok').length
  const others = services.filter((s) => !problems.includes(s))

  return (
    <Card title="Outside services" link={{ to: '/services', label: 'Details' }}>
      {!data && (error ? <Unavailable what="The status of outside services" /> : <Loading />)}
      {data && problems.length === 0 && (
        <>
          <Constellation services={services} />
          <p className="mt-3 text-center text-small font-medium">
            {fine === services.length ? 'All operational' : `${fine} of ${services.length} operational`}
          </p>
        </>
      )}
      {data && problems.length > 0 && (
        <div className="grid gap-3">
          {problems.slice(0, 2).map((s) => (
            <IncidentCard key={s.key} service={s} incident={headline(s)} />
          ))}
          {problems.length > 2 && (
            <p className="text-caption text-muted">And {problems.length - 2} more on the Services page.</p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            {others.map((s) => (
              <BrandLogo key={s.key} service={s} size={26} dim={s.state === 'unknown'} />
            ))}
            <span className="text-caption text-muted">
              {fine === others.length
                ? `The other ${others.length} are operational`
                : `${fine} of the other ${others.length} operational`}
            </span>
          </div>
        </div>
      )}
      {data && <ReadNotes services={services} />}
      {data?.stale && <StaleNote />}
    </Card>
  )
}
