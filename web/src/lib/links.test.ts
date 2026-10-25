import { serviceHost, serviceHref, serviceUrl } from './links'
import type { Hosts } from './types'

const HOSTS: Hosts = {
  as_of: '2026-09-30T12:00:00Z',
  stale: false,
  lan: '192.168.1.10',
  tailscale: { dns_name: 'dev-minotaur.tail1234.ts.net', ip: '100.70.0.10' },
}

describe('serviceHost', () => {
  it.each([
    ['192.168.1.10', '192.168.1.10'],
    ['100.70.0.10', '100.70.0.10'],
    ['dev-minotaur.tail1234.ts.net', 'dev-minotaur.tail1234.ts.net'],
  ])('reuses the host the hub was opened on (%s)', (pageHost, expected) => {
    expect(serviceHost(pageHost, HOSTS)).toBe(expected)
  })

  it('points at the NAS LAN address when the hub runs on this computer', () => {
    expect(serviceHost('localhost', HOSTS)).toBe('192.168.1.10')
  })

  it('falls back to the page host when the NAS addresses are unknown', () => {
    expect(serviceHost('localhost', undefined)).toBe('localhost')
  })
})

describe('serviceUrl', () => {
  it('builds port and path', () => {
    expect(serviceUrl({ port: 8096, path: '/' }, '192.168.1.10')).toBe('http://192.168.1.10:8096/')
    expect(serviceUrl({ port: 5984, path: '/_utils' }, 'nas')).toBe('http://nas:5984/_utils')
    expect(serviceUrl({ port: 5984, path: '_utils' }, 'nas')).toBe('http://nas:5984/_utils')
  })

  it('brackets IPv6 hosts', () => {
    expect(serviceUrl({ port: 80, path: '/' }, 'fd7a::1')).toBe('http://[fd7a::1]:80/')
  })
})

describe('serviceHref', () => {
  const SERVED: Hosts = {
    ...HOSTS,
    tailscale: { ...HOSTS.tailscale!, https_ports: { '8096': 18096, '8083': 443, '5984': 15984 } },
  }
  const jellyfin = { port: 8096, path: '/' }

  it('uses the HTTPS tailnet address on Tailscale when the service is served', () => {
    expect(serviceHref(jellyfin, 'dev-minotaur.tail1234.ts.net', SERVED)).toBe(
      'https://dev-minotaur.tail1234.ts.net:18096/',
    )
    // Also when the hub itself was opened on the Tailscale IP.
    expect(serviceHref({ port: 5984, path: '/_utils' }, '100.70.0.10', SERVED)).toBe(
      'https://dev-minotaur.tail1234.ts.net:15984/_utils',
    )
  })

  it('leaves out the default HTTPS port', () => {
    expect(serviceHref({ port: 8083, path: '/' }, '100.70.0.10', SERVED)).toBe(
      'https://dev-minotaur.tail1234.ts.net/',
    )
  })

  it('keeps plain HTTP for services that are not served, on the Tailscale IP, as ts.net always upgrades to HTTPS', () => {
    expect(serviceHref({ port: 8989, path: '/' }, 'dev-minotaur.tail1234.ts.net', SERVED)).toBe(
      `http://${HOSTS.tailscale!.ip}:8989/`,
    )
    // Opened on the IP already: it stays.
    expect(serviceHref({ port: 8989, path: '/' }, '100.70.0.10', SERVED)).toBe('http://100.70.0.10:8989/')
    // Without a known IP there is nothing better than the name.
    const noIp: Hosts = { ...SERVED, tailscale: { ...SERVED.tailscale!, ip: null } }
    expect(serviceHref({ port: 8989, path: '/' }, 'dev-minotaur.tail1234.ts.net', noIp)).toBe(
      'http://dev-minotaur.tail1234.ts.net:8989/',
    )
  })

  it('keeps LAN links at home and when nothing is known', () => {
    expect(serviceHref(jellyfin, '192.168.1.10', SERVED)).toBe('http://192.168.1.10:8096/')
    expect(serviceHref(jellyfin, '100.70.0.10', undefined)).toBe('http://100.70.0.10:8096/')
    expect(serviceHref(jellyfin, '100.70.0.10', HOSTS)).toBe('http://100.70.0.10:8096/')
  })
})

it('uses a link as is, whatever the connection', () => {
  const link = { port: null, path: '/', url: 'https://trash-guides.info' }
  expect(serviceHref(link, 'dev-minotaur.tail1234.ts.net', HOSTS)).toBe('https://trash-guides.info')
  expect(serviceHref(link, '192.168.1.10', HOSTS)).toBe('https://trash-guides.info')
})
