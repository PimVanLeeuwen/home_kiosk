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

/**
 * The link for a service. On Tailscale, a service published with `tailscale
 * serve` gets its HTTPS address on the tailnet name; everything else keeps the
 * plain HTTP link on the host the hub was opened on.
 */
export function serviceHref(
  service: Pick<Service, 'port' | 'path'>,
  pageHost: string,
  hosts?: Hosts,
): string {
  const tailnet = hosts?.tailscale
  const httpsPort = tailnet?.https_ports?.[String(service.port)]
  if (connectionFor(pageHost) === 'tailscale' && tailnet && httpsPort) {
    const path = service.path.startsWith('/') ? service.path : `/${service.path}`
    const port = httpsPort === 443 ? '' : `:${httpsPort}`
    return `https://${tailnet.dns_name}${port}${path}`
  }
  return serviceUrl(service, serviceHost(pageHost, hosts))
}
