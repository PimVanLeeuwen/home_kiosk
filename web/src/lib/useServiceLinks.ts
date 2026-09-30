import { serviceHref } from './links'
import type { Hosts, Service } from './types'
import { useApi } from './useApi'

/** Builds service links for this page; see serviceHref. */
export function useServiceLinks(): (service: Pick<Service, 'port' | 'path'>) => string {
  const hosts = useApi<Hosts>('/api/hosts')
  return (service) => serviceHref(service, window.location.hostname, hosts.data)
}
