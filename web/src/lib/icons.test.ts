import { ICON_NAMES, iconUrl } from './icons'

describe('bundled icons', () => {
  it('lists every file by name, SVG and PNG alike', () => {
    expect(ICON_NAMES).toEqual(expect.arrayContaining(['jellyfin', 'uptime-kuma', 'trash-guides']))
    expect(ICON_NAMES).not.toContain('LICENSE')
    // Small files are inlined as data URLs by Vite, larger ones get a hashed file.
    expect(iconUrl('jellyfin')).toMatch(/^(data:image\/svg\+xml|\/.*jellyfin)/)
    expect(iconUrl('trash-guides')).toMatch(/^(data:image\/png|\/.*trash-guides)/)
  })

  it('has no URL for unknown or empty names', () => {
    expect(iconUrl('grafana')).toBeUndefined()
    expect(iconUrl(null)).toBeUndefined()
  })
})
