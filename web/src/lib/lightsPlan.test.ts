import { planHeight, spots, type LightsPlan } from './lightsPlan'
import type { LightGroup } from './types'

const light = (id: string) => ({ id, name: id, on: true, brightness: 50, kelvin: null, reachable: true })
const group = (id: string, ids: string[]): LightGroup => ({ id, name: id, kind: 'white', on: true, brightness: 50, kelvin: null, lights: ids.map(light) })

describe('spots', () => {
  it('keeps placed lights and puts the others in a row along the top wall', () => {
    const plan: LightsPlan = { aspect: 2, lights: { a: { x: 0.9, y: 1.4 } }, furniture: [] }
    const at = spots(plan, [group('g1', ['a', 'b']), group('g2', ['c'])])
    expect(at.a).toEqual({ x: 0.9, y: 1 })
    expect(at.b).toEqual({ x: 1 / 3, y: 0.12 })
    expect(at.c).toEqual({ x: 2 / 3, y: 0.12 })
    expect(planHeight(2)).toBe(300)
  })
})
