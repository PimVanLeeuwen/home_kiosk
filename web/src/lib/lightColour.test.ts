import { whiteOf } from './lightColour'

describe('whiteOf', () => {
  it('runs from amber to white as the kelvin rises', () => {
    expect(whiteOf(2200)).toBe('rgb(255 146 39)')
    expect(whiteOf(6500)).toBe('rgb(255 254 250)')
    expect(whiteOf(4500)).toMatch(/^rgb\(255 2\d\d 1\d\d\)$/)
  })
})
