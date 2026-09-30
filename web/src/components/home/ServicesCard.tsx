import { uniqueMonograms } from '../../lib/monogram'
import type { Service } from '../../lib/types'
import { useServiceHost } from '../../lib/useServiceHost'
import { ServiceTile } from '../ServiceTile'
import { Card, Loading, Unavailable } from './Card'

interface Props {
  services: Service[] | undefined
  error: Error | undefined
}

export function ServicesCard({ services, error }: Props) {
  const host = useServiceHost()
  const labels = uniqueMonograms((services ?? []).map((s) => s.name))

  return (
    <Card title="Services" link={{ to: '/services', label: 'All' }} className="lg:col-span-2">
      {!services && (error ? <Unavailable what="The service list" /> : <Loading />)}
      {services && (
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
          {services.map((service, i) => (
            <li key={service.id}>
              <ServiceTile service={service} host={host} label={labels[i]} index={i} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
