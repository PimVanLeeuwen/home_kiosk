import { applyIntent, confirmed, pending } from './lightIntent'
import type { LightGroup } from './types'

const light = (id: string, on: boolean, brightness: number, kelvin: number | null = 4500, reachable = true) => ({
  id,
  name: id,
  on,
  brightness,
  kelvin,
  reachable,
})

function spots(levels: [boolean, number, number][], unreachable = ''): LightGroup {
  const lights = levels.map(([on, b, k], i) => light(`s${i}`, on, b, k, `s${i}` !== unreachable))
  const lit = lights.filter((l) => l.on)
  return {
    id: 'kitchen',
    name: 'Kitchen spots',
    kind: 'ambiance',
    on: lit.length > 0,
    brightness: lit.length ? Math.round(lit.reduce((n, l) => n + l.brightness, 0) / lit.length) : 50,
    kelvin: lights[0].kelvin,
    lights,
  }
}

const OLD = spots([
  [true, 77, 4500],
  [true, 77, 4500],
  [true, 77, 4500],
])

describe('lightIntent', () => {
  it('shows the asked state on the group and every reachable light', () => {
    const shown = applyIntent(spots([[true, 77, 4500], [true, 77, 4500], [false, 10, 4500]], 's2'), { brightness: 30, until: 1 })

    expect([shown.on, shown.brightness]).toEqual([true, 30])
    expect(shown.lights.map((l) => [l.on, l.brightness])).toEqual([
      [true, 30],
      [true, 30],
      [false, 10],
    ])
    expect(applyIntent(OLD, undefined)).toBe(OLD)
  })

  it('a white or a level switches on; off only switches off', () => {
    const off = spots([[false, 77, 4500], [false, 77, 4500], [false, 77, 4500]])

    expect(applyIntent(off, { kelvin: 2700, until: 1 })).toMatchObject({ on: true, kelvin: 2700 })
    expect(applyIntent(OLD, { on: false, until: 1 })).toMatchObject({ on: false, brightness: 77 })
  })

  it('is confirmed only once every light reports it', () => {
    const intent = { brightness: 30, until: 1 }
    const halfway = spots([[true, 30, 4500], [true, 77, 4500], [true, 77, 4500]])
    const done = spots([[true, 29.92, 4500], [true, 30.3, 4500], [true, 30, 4500]])

    expect(confirmed(OLD, intent)).toBe(false)
    expect(confirmed(halfway, intent)).toBe(false)
    expect(confirmed(done, intent)).toBe(true)
  })

  it('ignores an unreachable light, which cannot follow', () => {
    const group = spots([[false, 77, 4500], [true, 77, 4500], [false, 77, 4500]], 's1')

    expect(confirmed(group, { on: false, until: 1 })).toBe(true)
  })

  it('keeps waiting intents and drops confirmed or expired ones', () => {
    const intents = { kitchen: { on: false, until: 2_000 } }

    expect(pending(intents, [OLD], 1_000)).toEqual(intents)
    expect(pending(intents, [OLD], 2_000)).toEqual({})
    expect(pending(intents, [spots([[false, 77, 4500], [false, 77, 4500], [false, 77, 4500]])], 1_000)).toEqual({})
    expect(pending(intents, [], 1_000)).toEqual({})
  })
})
