import { serviceHost } from './links'
import type { Hosts } from './types'
import { useApi } from './useApi'

/** The host service links should use on this page; see serviceHost. */
export function useServiceHost(): string {
  const hosts = useApi<Hosts>('/api/hosts')
  return serviceHost(window.location.hostname, hosts.data)
}
