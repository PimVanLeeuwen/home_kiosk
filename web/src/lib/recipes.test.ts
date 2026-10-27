import { RECIPES } from '../test/recipeFixtures'
import { duration, filterRecipes, kilobytes, photoUrl } from './recipes'

const titles = (query: string, filter: Parameters<typeof filterRecipes>[2] = { kind: 'all' }) =>
  filterRecipes(RECIPES.recipes, query, filter).map((r) => r.title)

describe('recipes', () => {
  it('finds titles by every word typed, accents ignored', () => {
    expect(titles('creme')).toEqual(['Crème brûlée'])
    expect(titles('oven KIP')).toEqual(['Kip shoarma uit de oven'])
    expect(titles('  ')).toHaveLength(3)
    expect(titles('lasagne')).toEqual([])
  })

  it('filters by tag or by needing review', () => {
    expect(titles('', { kind: 'tag', tag: 'oven' })).toEqual(['Crème brûlée', 'Kip shoarma uit de oven'])
    expect(titles('', { kind: 'review' })).toEqual(['Dal met spinazie'])
    expect(titles('dal', { kind: 'tag', tag: 'oven' })).toEqual([])
  })

  it('writes durations in hours and minutes', () => {
    expect(duration(25)).toBe('25 min')
    expect(duration(120)).toBe('2 h')
    expect(duration(260)).toBe('4 h 20 min')
  })

  it('puts the photo stamp in the address', () => {
    expect(photoUrl({ id: 'crème-brulee', photo: '2026-10-27T18:00:00+00:00' }, 'thumb')).toBe(
      '/api/recipes/cr%C3%A8me-brulee/photo/thumb?v=2026-10-27T18%3A00%3A00%2B00%3A00',
    )
  })

  it('counts kilobytes, at least one', () => {
    expect(kilobytes('x')).toBe('1 kB')
    expect(kilobytes('x'.repeat(48 * 1024))).toBe('48 kB')
  })
})
