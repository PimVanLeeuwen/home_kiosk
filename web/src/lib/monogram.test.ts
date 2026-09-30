import { monogram, tileColour, TILE_COLOURS, uniqueMonograms } from './monogram'

describe('monogram', () => {
  it.each([
    ['Uptime Kuma', 'UK'],
    ['SABnzbd', 'SA'],
    ['CouchDB', 'CD'],
    ['Jellyfin', 'Je'],
    ['immich', 'Im'],
    ['X', 'X'],
    ['  ', '?'],
  ])('%s → %s', (name, expected) => {
    expect(monogram(name)).toBe(expected)
  })
})

describe('uniqueMonograms', () => {
  it('resolves clashes with later letters, keeping the first as is', () => {
    expect(
      uniqueMonograms(['Jellyfin', 'Jellyseerr', 'Transmission', 'Tracearr', 'Dozzle', 'Dockge']),
    ).toEqual(['Je', 'Jl', 'Tr', 'Ta', 'Do', 'Dc'])
  })

  it('leaves distinct names alone', () => {
    expect(uniqueMonograms(['Uptime Kuma', 'Sonarr', 'SABnzbd'])).toEqual(['UK', 'So', 'SA'])
  })

  it('keeps a clash when a name has no letters left to try', () => {
    expect(uniqueMonograms(['Ab', 'Ab', 'Ab'])).toEqual(['Ab', 'Ab', 'Ab'])
  })
})

describe('tileColour', () => {
  it('differs for neighbours and cycles through the palette', () => {
    expect(tileColour(0)).not.toBe(tileColour(1))
    expect(tileColour(TILE_COLOURS.length)).toBe(tileColour(0))
  })
})
