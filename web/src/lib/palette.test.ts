import { dataItems, loadRecent, pageItems, RECENT_KEY, saveRecent, search, type PaletteData } from './palette'
import type { ContainerLoad, Repo, Service } from './types'

const labels = (rows: ReturnType<typeof search>) => rows.map((r) => r.item.label)

describe('palette', () => {
  beforeEach(() => localStorage.clear())

  it('lists every page and Settings section, under their headings, without a query', () => {
    const rows = search(pageItems(), '', [])

    expect(rows[0]).toMatchObject({ heading: 'Pages', item: { label: 'Home', to: '/' } })
    const settings = rows.find((r) => r.heading === 'Settings')!
    expect(settings.item).toMatchObject({ label: 'Services', to: '/settings/services' })
    expect(rows).toHaveLength(pageItems().length)
  })

  it('puts recent choices first, without listing them twice', () => {
    const rows = search(pageItems(), '', ['page:/backups', 'settings:feeds'])

    expect(labels(rows).slice(0, 2)).toEqual(['Backups', 'News feeds'])
    expect(rows[0].heading).toBe('Recent')
    expect(labels(rows).filter((l) => l === 'Backups')).toHaveLength(1)
  })

  it('finds by a few letters, best first', () => {
    expect(labels(search(pageItems(), 'bk', []))[0]).toBe('Backups')
    expect(labels(search(pageItems(), 'desk', []))[0]).toBe('Desk panels')
    expect(search(pageItems(), 'zzz', [])).toEqual([])
  })

  it('also matches the description and "settings", the label counting most', () => {
    expect(labels(search(pageItems(), 'hue', []))).toContain('Lights')
    const music = search(pageItems(), 'music', [])
    expect(labels(music).slice(0, 2)).toEqual(['Music', 'Music'])
    expect(music[0].item.group).toBe('Pages')
    expect(search(pageItems(), 'settings music', [])[0].item.to).toBe('/settings/music')
  })

  it('remembers the last five choices, newest first', () => {
    for (const id of ['a', 'b', 'c', 'd', 'e', 'f', 'b']) saveRecent(id)

    expect(loadRecent()).toEqual(['b', 'f', 'e', 'd', 'c'])
  })

  it('survives a broken store', () => {
    localStorage.setItem(RECENT_KEY, '{nope')
    expect(loadRecent()).toEqual([])
  })
})

describe('palette matching beyond the label', () => {
  it('needs the words typed, not scattered letters, in a description', () => {
    const found = search(pageItems(), 'set', []).map((r) => r.item.label)

    expect(found).toContain('Settings')
    expect(found).toContain('Desk panels')
    expect(found).not.toContain('Alerts')
    expect(found).not.toContain('Lights')
  })
})

const service = (id: string, extra: Partial<Service> = {}): Service => ({
  id, name: id[0].toUpperCase() + id.slice(1), group: 'Media', description: `${id} app`, port: 8096, path: '/',
  container: id, widget: null, icon: null, status: 'up', ...extra,
})
const DATA: PaletteData = {
  services: { as_of: null, stale: false, groups: [{ name: 'Media', services: [
    service('jellyfin', { icon: 'jellyfin' }),
    service('dozzle', { port: 8081, group: 'Monitoring' }),
    service('github', { port: null, url: 'https://github.com/someone', container: null }),
  ] }] },
  repos: { as_of: '', stale: false, groups: [{ login: 'someone', label: 'You', error: null, repos: [
    { name: 'home_kiosk', full_name: 'someone/home_kiosk', url: 'https://github.com/someone/home_kiosk', description: 'The hub' } as Repo,
  ] }] },
  docker: { as_of: '', stale: false, cpu_pct: 0, mem_bytes: 0, containers: [
    { name: 'paperless-bridge', project: 'paperless', state: 'running' } as ContainerLoad,
    { name: 'old one', project: null, state: 'exited' } as ContainerLoad,
  ] },
}

describe('palette data rows', () => {
  it('links services as their tiles do, external links as they are', () => {
    const rows = dataItems(DATA, '192.168.1.10')
    const jellyfin = rows.find((r) => r.id === 'service:jellyfin')!

    expect(jellyfin).toMatchObject({ group: 'Services', href: 'http://192.168.1.10:8096/', hint: 'jellyfin app', searchOnly: true })
    expect(jellyfin.image).toBeTruthy()
    expect(rows.find((r) => r.id === 'service:github')!.href).toBe('https://github.com/someone')
  })

  it('opens a repo on GitHub, under its owner', () => {
    const repo = dataItems(DATA, 'nas').find((r) => r.group === 'Repos')!

    expect(repo).toMatchObject({ label: 'home_kiosk', hint: 'You · The hub', href: 'https://github.com/someone/home_kiosk' })
  })

  it('opens a container’s logs in Dozzle by name, with its stack and when it is not running', () => {
    const rows = dataItems(DATA, 'nas').filter((r) => r.group === 'Containers')

    expect(rows[0]).toMatchObject({ label: 'paperless-bridge', hint: 'Logs in Dozzle · paperless', href: 'http://nas:8081/show?name=paperless-bridge' })
    expect(rows[1]).toMatchObject({ hint: 'Logs in Dozzle · exited', href: 'http://nas:8081/show?name=old%20one' })
  })

  it('leaves containers out without Dozzle in the catalog', () => {
    const services = { ...DATA.services!, groups: [{ name: 'Media', services: [service('jellyfin')] }] }

    expect(dataItems({ ...DATA, services }, 'nas').some((r) => r.group === 'Containers')).toBe(false)
  })

  it('shows data rows only when searching, or as recent', () => {
    const items = [...pageItems(), ...dataItems(DATA, 'nas')]

    expect(search(items, '', []).some((r) => r.item.searchOnly)).toBe(false)
    expect(search(items, '', ['service:jellyfin'])[0].item.label).toBe('Jellyfin')
    expect(search(items, 'jelly', [])[0].item.id).toBe('service:jellyfin')
    expect(search(items, 'bridge', [])[0].item.id).toBe('container:paperless-bridge')
    expect(search(items, 'kiosk', [])[0].item.id).toBe('repo:someone/home_kiosk')
  })
})
