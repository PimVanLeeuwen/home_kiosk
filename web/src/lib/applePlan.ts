import type { AppleDevices } from './types'

/** The plan's drawing box (SVG units). */
export const W = 100
export const H = 72
const GAP = 3
const TOP_HEIGHT = 36
/** Lines stop this far from an orb's centre, outside its ring and icon. */
const EDGE = 6.6

type Room = AppleDevices['rooms'][number]

export interface Zone {
  room: Room
  x: number
  y: number
  w: number
  h: number
  /** Where the room's name goes: at the top of the first room, at the bottom of the others, so no line crosses it. */
  labelAt: 'top' | 'bottom'
}

export interface Orb {
  room: Room
  device: Room['devices'][number]
  x: number
  y: number
}

/**
 * The house as zones: the first room across the top, the others side by side
 * below it, each as wide as its share of their devices. One room fills the box.
 */
export function zones(rooms: Room[]): Zone[] {
  if (rooms.length === 0) return []
  const [first, ...rest] = rooms
  if (rest.length === 0) return [{ room: first, x: 2, y: 2, w: W - 4, h: H - 4, labelAt: 'top' }]
  const top: Zone = { room: first, x: 2, y: 2, w: W - 4, h: TOP_HEIGHT, labelAt: 'top' }
  const y = 2 + TOP_HEIGHT + GAP
  const h = H - 2 - y
  const total = rest.reduce((n, r) => n + Math.max(1, r.devices.length), 0)
  const free = W - 4 - GAP * (rest.length - 1)
  let x = 2
  const below = rest.map((room) => {
    const w = (free * Math.max(1, room.devices.length)) / total
    const zone: Zone = { room, x, y, w, h, labelAt: 'bottom' }
    x += w + GAP
    return zone
  })
  return [top, ...below]
}

/** Each room's devices on one line across its zone, evenly spaced. */
export function orbs(zs: Zone[]): Orb[] {
  return zs.flatMap((z) => {
    const n = z.room.devices.length
    // Below the top label, above the bottom one.
    const y = z.labelAt === 'top' ? z.y + z.h * 0.56 : z.y + z.h * 0.45
    return z.room.devices.map((device, i) => ({ room: z.room, device, x: z.x + (z.w * (i + 0.5)) / n, y }))
  })
}

/**
 * The Thread border routers as one network: neighbours in a room joined, each
 * lower room's first router joined to the nearest router above, and the lower
 * rooms joined to each other. The hub cannot see the real radio links.
 */
export function threadLinks(all: Orb[]): [Orb, Orb][] {
  const routers = all.filter((o) => o.device.thread !== null)
  const byRoom = new Map<string, Orb[]>()
  for (const o of routers) byRoom.set(o.room.id, [...(byRoom.get(o.room.id) ?? []), o])
  const groups = [...byRoom.values()]
  const links: [Orb, Orb][] = []
  for (const g of groups) for (let i = 1; i < g.length; i++) links.push([g[i - 1], g[i]])
  const [top, ...lower] = groups
  if (!top) return links
  lower.forEach((g, i) => {
    if (i === 0) {
      const nearest = [...top].sort((a, b) => Math.abs(a.x - g[0].x) - Math.abs(b.x - g[0].x))[0]
      links.push([nearest, g[0]])
    } else {
      links.push([lower[i - 1].at(-1)!, g[0]])
    }
  })
  // The last lower room also hangs on the router above it nearest to it, closing the loop.
  if (lower.length > 1) {
    const last = lower.at(-1)!.at(-1)!
    const nearest = [...top].sort((a, b) => Math.abs(a.x - last.x) - Math.abs(b.x - last.x))[0]
    if (!links.some(([a, b]) => (a === nearest && b === last) || (a === last && b === nearest))) links.push([nearest, last])
  }
  return links
}

/** A gentle curve between two orbs that stops at their edges, never crossing an icon. */
export function curve(a: { x: number; y: number }, b: { x: number; y: number }, k = 0.16): string {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const cx = (a.x + b.x) / 2 - dy * k
  const cy = (a.y + b.y) / 2 + dx * k
  const edge = (p: { x: number; y: number }) => {
    const vx = cx - p.x
    const vy = cy - p.y
    const l = Math.hypot(vx, vy) || 1
    return [p.x + (vx / l) * EDGE, p.y + (vy / l) * EDGE]
  }
  const [sx, sy] = edge(a)
  const [ex, ey] = edge(b)
  const f = (n: number) => n.toFixed(1)
  return `M${f(sx)} ${f(sy)} Q${f(cx)} ${f(cy)} ${f(ex)} ${f(ey)}`
}
