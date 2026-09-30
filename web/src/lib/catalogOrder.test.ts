import { groupEntries, moveGroup, moveService } from './catalogOrder'

const ENTRIES = [
  { id: 'jellyfin', group: 'Media' },
  { id: 'immich', group: 'Media' },
  { id: 'sonarr', group: 'Arr' },
  { id: 'radarr', group: 'Arr' },
  { id: 'tandoor', group: 'Apps' },
]

describe('groupEntries', () => {
  it('keeps catalog order', () => {
    expect(groupEntries(ENTRIES).map((g) => [g.name, g.items.length])).toEqual([
      ['Media', 2],
      ['Arr', 2],
      ['Apps', 1],
    ])
  })
})

describe('moveService', () => {
  it('swaps with the neighbour inside its group', () => {
    expect(moveService(ENTRIES, 'radarr', -1)).toEqual([
      'jellyfin',
      'immich',
      'radarr',
      'sonarr',
      'tandoor',
    ])
  })

  it('never crosses into another group', () => {
    const unchanged = ENTRIES.map((e) => e.id)
    expect(moveService(ENTRIES, 'sonarr', -1)).toEqual(unchanged)
    expect(moveService(ENTRIES, 'immich', 1)).toEqual(unchanged)
    expect(moveService(ENTRIES, 'tandoor', 1)).toEqual(unchanged)
  })
})

describe('moveGroup', () => {
  it('swaps whole groups', () => {
    expect(moveGroup(ENTRIES, 'Arr', -1)).toEqual([
      'sonarr',
      'radarr',
      'jellyfin',
      'immich',
      'tandoor',
    ])
  })

  it('is unchanged at the edges', () => {
    const unchanged = ENTRIES.map((e) => e.id)
    expect(moveGroup(ENTRIES, 'Media', -1)).toEqual(unchanged)
    expect(moveGroup(ENTRIES, 'Apps', 1)).toEqual(unchanged)
  })
})
