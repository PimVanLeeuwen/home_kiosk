import { deviceKind, MAP_CENTRE, MAP_W, mapLine, mapPositions, osName, relayName } from './tailnet'

describe('tailnet', () => {
  it('names relays and systems, keeping what it does not know', () => {
    expect(relayName('ams')).toBe('Amsterdam')
    expect(relayName('xyz')).toBe('XYZ')
    expect(osName('windows')).toBe('Windows')
    expect(osName('macOS')).toBe('macOS')
  })

  it('tells the kind of device by its system, and an iPad by its name', () => {
    expect(deviceKind({ os: 'macOS', name: 'pim-macbook' })).toBe('laptop')
    expect(deviceKind({ os: 'iOS', name: 'pim-iphone' })).toBe('phone')
    expect(deviceKind({ os: 'iOS', name: 'iPad' })).toBe('tablet')
    expect(deviceKind({ os: 'tvOS', name: 'appletv' })).toBe('tv')
    expect(deviceKind({ os: 'windows', name: 'desk-pc' })).toBe('desktop')
    expect(deviceKind({ os: 'linux', name: 'nas' })).toBe('server')
  })

  it('spreads devices evenly round the NAS, four taking the corners', () => {
    const four = mapPositions(4)
    expect(four).toHaveLength(4)
    const [tl, tr, br, bl] = four
    expect(tl.x).toBeLessThan(MAP_CENTRE.x)
    expect(tl.y).toBeLessThan(MAP_CENTRE.y)
    expect(tr.x).toBeGreaterThan(MAP_CENTRE.x)
    expect(br.y).toBeGreaterThan(MAP_CENTRE.y)
    expect(bl.x).toBeLessThan(MAP_CENTRE.x)
    // Mirror images: the same distance from the middle.
    expect(tl.x + tr.x).toBeCloseTo(2 * MAP_CENTRE.x, 0)
    expect(mapPositions(0)).toEqual([])
  })

  it('stops a line short of both tiles', () => {
    const line = mapLine({ x: 90, y: MAP_CENTRE.y })
    const centre = (MAP_CENTRE.x / 100) * MAP_W
    const device = 0.9 * MAP_W
    expect(line.y1).toBeCloseTo(line.y2)
    // Past the NAS tile's edge (14% of the width, half of it each side) and before the device's (10%).
    expect(line.x1).toBeGreaterThan(centre + 0.07 * MAP_W)
    expect(line.x2).toBeLessThan(device - 0.05 * MAP_W)
    expect(line.x2).toBeGreaterThan(line.x1)
  })
})
