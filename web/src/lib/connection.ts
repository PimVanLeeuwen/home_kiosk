export type Connection = 'tailscale' | 'lan' | 'local'

export const CONNECTION_LABEL: Record<Connection, string> = {
  tailscale: 'Tailscale',
  lan: 'Local network',
  local: 'This computer',
}

/** Tailscale hands out addresses from the CGNAT range 100.64.0.0/10. */
function isTailscaleIp(host: string): boolean {
  const parts = host.split('.')
  if (parts.length !== 4 || !parts.every((p) => /^\d{1,3}$/.test(p))) return false
  const [a, b] = parts.map(Number)
  return a === 100 && b >= 64 && b <= 127
}

/**
 * How the hub was reached, from the hostname in the address bar. Decides which
 * host the service links use, so it has to work without asking the server.
 */
export function connectionFor(hostname: string): Connection {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '')
  if (host.endsWith('.ts.net') || isTailscaleIp(host)) return 'tailscale'
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1') return 'local'
  return 'lan'
}
