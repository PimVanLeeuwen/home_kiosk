import { MORE_ITEMS, NAV_ITEMS, TAB_ITEMS, TAB_ROUTES } from './navigation'

describe('navigation', () => {
  it('gives every section a unique route', () => {
    const routes = NAV_ITEMS.map((item) => item.to)
    expect(new Set(routes).size).toBe(routes.length)
  })

  it('puts every section either in the tab bar or under More, never both', () => {
    expect(TAB_ITEMS.map((item) => item.to)).toEqual(TAB_ROUTES)
    expect([...TAB_ITEMS, ...MORE_ITEMS]).toHaveLength(NAV_ITEMS.length)
    expect(MORE_ITEMS.some((item) => TAB_ROUTES.includes(item.to))).toBe(false)
  })

  it('keeps the tab bar to four sections plus More', () => {
    expect(TAB_ITEMS).toHaveLength(4)
  })
})
