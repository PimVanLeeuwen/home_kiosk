import { MORE_ITEMS, NAV_ITEMS, OLD_PATH, SPACES, TAB_SPACES, spaceOf, spacePath } from './navigation'
import { MOVED, PATHS, movedPath } from './paths'

describe('navigation (the spaces, plan.md M38)', () => {
  it('gives every page a unique address', () => {
    const routes = NAV_ITEMS.map((item) => item.to)
    expect(new Set(routes).size).toBe(routes.length)
  })

  it('has six spaces, each page under its own space', () => {
    expect(SPACES.map((s) => s.label)).toEqual(['Now', 'Home', 'House', 'Read', 'Money', 'Kitchen'])
    for (const space of SPACES) {
      for (const tab of space.tabs) {
        if (tab.to !== '/' && tab.to !== `/${space.id}`) expect(tab.to.startsWith(`/${space.id}/`)).toBe(true)
        expect(spaceOf(tab.to)).toBe(space)
      }
    }
    expect(SPACES.find((s) => s.id === 'house')!.tabs.map((t) => t.label)).toEqual([
      'Overview', 'NAS', 'Docker', 'Services', 'Outside', 'Backups', 'Media', 'Network', 'Repos', 'Alerts',
    ])
    // 5f: the Air, Laundry and Apple devices cards got pages of their own in Home.
    expect(SPACES.find((s) => s.id === 'home')!.tabs.map((t) => t.label)).toEqual(['Lights', 'Music', 'Air', 'Laundry', 'Apple devices'])
  })

  it('finds the space of a page under a tab and of the space address itself', () => {
    expect(spaceOf('/house/alerts/7')?.id).toBe('house')
    expect(spaceOf('/kitchen/recipes/kip/cook')?.id).toBe('kitchen')
    expect(spaceOf('/house')?.id).toBe('house')
    expect(spaceOf('/now')?.id).toBe('now')
    expect(spaceOf('/')?.id).toBe('now')
    expect(spaceOf('/ask')).toBeUndefined()
    expect(spaceOf('/settings/feeds')).toBeUndefined()
    expect(spaceOf('/housekeeping')).toBeUndefined()
  })

  it('opens a space on its first tab', () => {
    expect(SPACES.map(spacePath)).toEqual(['/', PATHS.lights, '/house', PATHS.news, PATHS.portfolio, PATHS.recipes])
  })

  it('puts four spaces in the phone tab bar and the rest, with Ask and Settings, under More', () => {
    expect(TAB_SPACES).toEqual(['now', 'home', 'house', 'read'])
    expect(MORE_ITEMS.map((item) => item.label)).toEqual(['Portfolio', 'Recipes', 'Ask', 'Settings'])
  })

  it('moves every old page address to a page that exists', () => {
    const pages = new Set(NAV_ITEMS.map((item) => item.to))
    for (const to of Object.values(MOVED)) expect(pages.has(to)).toBe(true)
    expect(OLD_PATH[PATHS.network]).toBe('/tailscale')
  })

  it('rewrites an old address, keeping what is under it, its query and hash', () => {
    expect(movedPath('/nas')).toBe('/house/nas')
    expect(movedPath('/alerts/12')).toBe('/house/alerts/12')
    expect(movedPath('/portfolio?h=YAHOO%2FNVDA')).toBe('/money/portfolio?h=YAHOO%2FNVDA')
    expect(movedPath('/nas#disks')).toBe('/house/nas#disks')
    expect(movedPath('/newsletter')).toBe('/newsletter')
    expect(movedPath('/settings/feeds')).toBe('/settings/feeds')
  })
})
