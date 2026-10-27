import { RECIPES, SHOARMA } from '../test/recipeFixtures'
import { amountText, duration, filterRecipes, firstCook, ingredientTotals, kilobytes, photoUrl } from './recipes'

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

describe('amounts', () => {
  it.each([
    [null, '', 1, 'naar smaak'],
    [500, 'g', 1, '500 g'],
    [500, 'g', 2, '1 kg'],
    [750, 'g', 2, '1,5 kg'],
    [33, 'g', 1.5, '50 g'],
    [12, 'g', 1.5, '18 g'],
    [0.25, 'tl', 1, '¼ tl'],
    [0.25, 'tl', 2, '½ tl'],
    [0.5, '', 3, '1½'],
    [1, 'teen', 1, '1 teen'],
    [2, 'teen', 1, '2 tenen'],
    [1, 'el', 2.5, '2½ el'],
    [1, 'el', 1.2, '1,2 el'],
    [0.3, 'l', 1, '0,3 l'],
    [1, 'bosje', 0.5, '½ bosje'],
  ])('%s %s times %s is "%s"', (amount, unit, factor, text) => {
    expect(amountText(amount, unit, factor)).toBe(text)
  })

  it('sums each ingredient per unit and splits get from check', () => {
    const totals = ingredientTotals(SHOARMA)
    expect(totals.find((t) => t.name === 'Griekse yoghurt')).toEqual({ name: 'Griekse yoghurt', pantry: false, text: '3 el + 150 g' })
    // An amount wins over "naar smaak" for the same thing.
    expect(totals.find((t) => t.name === 'zout')?.text).toBe('1 tl')
    expect(totals.find((t) => t.name === 'knoflook')?.text).toBe('3 tenen')
    expect(ingredientTotals(SHOARMA, 2).find((t) => t.name === 'kippendijen')?.text).toBe('1 kg')
    expect(totals.filter((t) => t.pantry).map((t) => t.name)).toEqual(['olijfolie', 'knoflook', 'komijn', 'gerookt paprikapoeder', 'kaneel', 'zout'])
  })

  it('finds where the heat starts', () => {
    expect(firstCook(SHOARMA)).toBe(2)
    expect(firstCook({ ...SHOARMA, phases: SHOARMA.phases.slice(2) })).toBe(-1)
  })
})
