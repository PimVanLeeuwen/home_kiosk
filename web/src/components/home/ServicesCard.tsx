import { uniqueMonograms } from '../../lib/monogram'
import type { Service } from '../../lib/types'
import { useServiceLinks } from '../../lib/useServiceLinks'
import { ServiceTile } from '../ServiceTile'
import { Card } from '../ui/Card'
import { Loading, Unavailable } from '../ui/states'

interface Props {
  services: Service[] | undefined
  error: Error | undefined
}

export function ServicesCard({ services, error }: Props) {
  const linkFor = useServiceLinks()
  const labels = uniqueMonograms((services ?? []).map((s) => s.name))

  return (
    <Card title="Services" link={{ to: '/services', label: 'All' }}>
      {!services && (error ? <Unavailable what="The service list" /> : <Loading />)}
      {services && (
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
          {services.map((service, i) => (
            <li key={service.id}>
              <ServiceTile service={service} href={linkFor(service)} label={labels[i]} index={i} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
