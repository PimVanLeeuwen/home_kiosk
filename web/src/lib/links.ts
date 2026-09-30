import { connectionFor } from './connection'
import type { Hosts, Service } from './types'

/**
 * The host a service link should use.
 *
 * Whatever host the hub was opened on is already known to work from this
 * device, so links reuse it: the LAN IP at home, the Tailscale name or IP when
 * remote. Only when the hub runs somewhere else (a laptop in development) do
 * the NAS's own addresses from /api/hosts come in.
 */
export function serviceHost(pageHost: string, hosts?: Hosts): string {
  if (connectionFor(pageHost) !== 'local') return pageHost
  return hosts?.lan ?? pageHost
}

export function serviceUrl(service: Pick<Service, 'port' | 'path'>, host: string): string {
  const path = service.path.startsWith('/') ? service.path : `/${service.path}`
  // IPv6 literals need brackets in a URL.
  const hostPart = host.includes(':') && !host.startsWith('[') ? `[${host}]` : host
  return `http://${hostPart}:${service.port}${path}`
}
