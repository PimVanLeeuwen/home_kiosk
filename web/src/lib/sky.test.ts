import { skyLights } from './sky'

describe('skyLights', () => {
  it('follows the time of day', () => {
    const glow = (hour: number) => skyLights(hour)[0]
    expect(glow(2)).toBe(glow(22)) // night
    expect(new Set([glow(2), glow(7), glow(12), glow(19)]).size).toBe(4)
    expect(glow(6)).toBe(glow(8)) // dawn starts at six
    expect(glow(9)).toBe(glow(16)) // day
    expect(glow(17)).toBe(glow(20)) // dusk
  })
})
