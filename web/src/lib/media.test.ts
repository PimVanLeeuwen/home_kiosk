import { byDay, episodeCode, upcomingDay } from './media'
import type { MediaEpisode } from './types'

const NOW = new Date(2026, 9, 14, 10, 0) // a Wednesday
const ep = (series: string, day: number, hour: number): MediaEpisode => ({
  series, season: 1, episode: 2, title: '', air_date: new Date(2026, 9, day, hour).toISOString(), poster: null,
})

describe('media', () => {
  it('heads the week ahead with Today, Tomorrow, then the weekday', () => {
    expect(upcomingDay(new Date(2026, 9, 14, 21).toISOString(), NOW)).toBe('Today')
    expect(upcomingDay(new Date(2026, 9, 15, 3).toISOString(), NOW)).toBe('Tomorrow')
    expect(upcomingDay(new Date(2026, 9, 19, 21).toISOString(), NOW)).toBe('Monday')
  })

  it('groups episodes by day in their order', () => {
    const groups = byDay([ep('A', 14, 21), ep('B', 16, 3), ep('C', 16, 22)], NOW)

    expect(groups.map(([day, eps]) => [day, eps.map((e) => e.series)])).toEqual([
      ['Today', ['A']],
      ['Friday', ['B', 'C']],
    ])
  })

  it('writes episode codes', () => {
    expect(episodeCode({ season: 3, episode: 2 })).toBe('S3 E2')
  })
})
