import { connectionFor } from './connection'

describe('connectionFor', () => {
  it.each([
    ['minotaur.tail1234.ts.net', 'tailscale'],
    ['MINOTAUR.TAIL1234.TS.NET', 'tailscale'],
    ['100.70.0.10', 'tailscale'],
    ['100.64.0.1', 'tailscale'],
    ['100.127.255.254', 'tailscale'],
    ['192.168.1.10', 'lan'],
    ['100.63.0.1', 'lan'], // just below the Tailscale range
    ['100.128.0.1', 'lan'], // just above it
    ['nas.local', 'lan'],
    ['localhost', 'local'],
    ['127.0.0.1', 'local'],
    ['[::1]', 'local'],
  ])('%s is %s', (host, expected) => {
    expect(connectionFor(host)).toBe(expected)
  })
})
