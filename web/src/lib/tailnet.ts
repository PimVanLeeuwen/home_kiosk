import type { TailnetDevice } from './types'

/** Tailscale's DERP relays by region code; an unknown code shows as itself. */
const RELAYS: Record<string, string> = {
  ams: 'Amsterdam', fra: 'Frankfurt', lhr: 'London', par: 'Paris', mad: 'Madrid', waw: 'Warsaw',
  hel: 'Helsinki', nue: 'Nuremberg', nyc: 'New York', sfo: 'San Francisco', sea: 'Seattle',
  ord: 'Chicago', dfw: 'Dallas', den: 'Denver', mia: 'Miami', tor: 'Toronto', sao: 'São Paulo',
  sin: 'Singapore', syd: 'Sydney', tok: 'Tokyo', hkg: 'Hong Kong', blr: 'Bangalore', jnb: 'Johannesburg',
}

export const relayName = (code: string) => RELAYS[code] ?? code.toUpperCase()

/** tailscaled says "windows", "linux"; Apple's systems come capitalised already. */
const OS_NAMES: Record<string, string> = { windows: 'Windows', linux: 'Linux', android: 'Android', freebsd: 'FreeBSD' }

export const osName = (os: string) => OS_NAMES[os] ?? os

export type DeviceKind = 'laptop' | 'phone' | 'tablet' | 'tv' | 'desktop' | 'server'

/** What kind of device it is, for its icon; an iPad reports iOS, so its name decides. */
export function deviceKind(device: Pick<TailnetDevice, 'os' | 'name'>): DeviceKind {
  if (/ipad|tablet/i.test(device.name)) return 'tablet'
  switch (device.os) {
    case 'macOS':
      return 'laptop'
    case 'iOS':
    case 'android':
      return 'phone'
    case 'tvOS':
      return 'tv'
    case 'windows':
      return 'desktop'
    default:
      return 'server'
  }
}

/** The map's own proportions; the SVG's viewBox and the nodes share them. */
export const MAP_W = 155
export const MAP_H = 100
export const MAP_CENTRE = { x: 50, y: 48 }
/** Tile sizes as a share of the map's width, so lines and tiles scale together. */
export const PEER_TILE = 0.1
export const SELF_TILE = 0.14
/** Room between a line's end and a tile, in viewBox units. */
const GAP = 2

/**
 * Where each device sits, in percent of the map: evenly round an ellipse
 * around the NAS, starting top left, so four devices take the corners.
 */
export function mapPositions(count: number): { x: number; y: number }[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = ((-90 - 180 / count + (360 / count) * i) * Math.PI) / 180
    return {
      x: Math.round((MAP_CENTRE.x + 40 * Math.cos(angle)) * 10) / 10,
      y: Math.round((MAP_CENTRE.y + 39 * Math.sin(angle)) * 10) / 10,
    }
  })
}

/** A line from the NAS to a device, in viewBox units, stopping short of both tiles. */
export function mapLine(to: { x: number; y: number }) {
  const x0 = (MAP_CENTRE.x / 100) * MAP_W
  const y0 = (MAP_CENTRE.y / 100) * MAP_H
  const x1 = (to.x / 100) * MAP_W
  const y1 = (to.y / 100) * MAP_H
  const length = Math.hypot(x1 - x0, y1 - y0) || 1
  const ux = (x1 - x0) / length
  const uy = (y1 - y0) / length
  // Square tiles: reach the edge along the line, not just the half width.
  const edge = (size: number) => ((size * MAP_W) / 2) / Math.max(Math.abs(ux), Math.abs(uy)) + GAP
  const from = edge(SELF_TILE)
  const until = edge(PEER_TILE)
  const r = (n: number) => Math.round(n * 10) / 10
  return { x1: r(x0 + ux * from), y1: r(y0 + uy * from), x2: r(x1 - ux * until), y2: r(y1 - uy * until) }
}
