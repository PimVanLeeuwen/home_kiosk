import { serviceHost, serviceUrl } from './links'
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
