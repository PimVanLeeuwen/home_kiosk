import { loadRecent, pageItems, RECENT_KEY, saveRecent, search } from './palette'

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
