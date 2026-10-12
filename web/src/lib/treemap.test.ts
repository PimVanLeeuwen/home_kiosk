import { squarify } from './treemap'

const area = (t: { w: number; h: number }) => t.w * t.h

describe('squarify', () => {
  it('fills the box exactly, each tile in proportion to its weight', () => {
    const weights = [6, 6, 4, 3, 2, 2, 1]
    const tiles = squarify(weights, (n) => n, 600, 400)

    expect(tiles).toHaveLength(7)
    const total = tiles.reduce((s, t) => s + area(t), 0)
    expect(total).toBeCloseTo(600 * 400)
    tiles.forEach((t, i) => expect(area(t) / total).toBeCloseTo(weights[i] / 24))
    // Nothing leaves the box.
    tiles.forEach((t) => {
      expect(t.x + t.w).toBeLessThanOrEqual(600 + 1e-6)
      expect(t.y + t.h).toBeLessThanOrEqual(400 + 1e-6)
    })
  })

  it('keeps tiles close to square rather than slicing them thin', () => {
    const tiles = squarify([6, 6, 4, 3, 2, 2, 1], (n) => n, 600, 400)
    const worst = Math.max(...tiles.map((t) => Math.max(t.w / t.h, t.h / t.w)))
    expect(worst).toBeLessThan(3)
  })

  it('returns nothing for no items, no weight or no room', () => {
    expect(squarify([], (n: number) => n, 100, 100)).toEqual([])
    expect(squarify([0, 0], (n) => n, 100, 100)).toEqual([])
    expect(squarify([1], (n) => n, 0, 100)).toEqual([])
  })
})
