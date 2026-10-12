import { skyGlow } from './sky'

describe('skyGlow', () => {
  it('follows the time of day', () => {
    expect(skyGlow(2)).toBe(skyGlow(22)) // night
    expect(new Set([skyGlow(2), skyGlow(7), skyGlow(12), skyGlow(19)]).size).toBe(4)
    expect(skyGlow(6)).toBe(skyGlow(8)) // dawn starts at six
    expect(skyGlow(9)).toBe(skyGlow(16)) // day
    expect(skyGlow(17)).toBe(skyGlow(20)) // dusk
  })
})
