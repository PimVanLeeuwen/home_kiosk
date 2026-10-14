import { curve, H, orbs, threadLinks, W, zones } from './applePlan'
import type { AppleDevices } from './types'

type Room = AppleDevices['rooms'][number]
const dev = (id: string, thread: boolean | null = true) => ({ id, name: id, kind: 'homepod' as const, online: true, offline_since: null, thread })
const room = (id: string, devices: ReturnType<typeof dev>[]): Room => ({ id, name: id, devices, playing: null })

const HOUSE = [
  room('living', [dev('w1'), dev('tv1'), dev('w2')]),
  room('bedroom', [dev('tv2', null), dev('mini1')]),
  room('bath', [dev('mini2')]),
]

describe('applePlan', () => {
  it('puts the first room across the top and shares the bottom by devices', () => {
    const [top, bed, bath] = zones(HOUSE)

    expect([top.x, top.y, top.w, top.labelAt]).toEqual([2, 2, W - 4, 'top'])
    expect(bed.labelAt).toBe('bottom')
    expect(bed.w / bath.w).toBeCloseTo(2)
    expect(bath.x + bath.w).toBeCloseTo(W - 2)
    expect(bed.y + bed.h).toBeCloseTo(H - 2)
  })

  it('lets a single room fill the plan', () => {
    expect(zones([HOUSE[2]])[0]).toMatchObject({ x: 2, y: 2, w: W - 4, h: H - 4 })
    expect(zones([])).toEqual([])
  })

  it('spaces the devices evenly inside their room', () => {
    const living = orbs(zones(HOUSE)).filter((o) => o.room.id === 'living')

    expect(living.map((o) => Math.round(o.x))).toEqual([18, 50, 82])
    expect(new Set(living.map((o) => o.y)).size).toBe(1)
  })

  it('joins only the border routers, as one network', () => {
    const links = threadLinks(orbs(zones(HOUSE))).map(([a, b]) => `${a.device.id}-${b.device.id}`)

    expect(links).toEqual(['w1-tv1', 'tv1-w2', 'tv1-mini1', 'mini1-mini2', 'w2-mini2'])
  })

  it('stops a line at the edge of both orbs', () => {
    const [start, end] = curve({ x: 10, y: 10 }, { x: 50, y: 10 })
      .match(/^M([\d.]+) ([\d.]+) Q[\d. ]+ ([\d.]+) ([\d.]+)$/)!
      .slice(1)
      .map(Number)
      .reduce<number[][]>((pairs, n, i) => (i % 2 ? (pairs.at(-1)!.push(n), pairs) : [...pairs, [n]]), [])

    expect(Math.hypot(start[0] - 10, start[1] - 10)).toBeCloseTo(6.6, 0)
    expect(Math.hypot(end[0] - 50, end[1] - 10)).toBeCloseTo(6.6, 0)
  })
})
