import { daySummary, hoursOf, skyOf, stampTime, type ForecastDay } from './weatherTypes'

const day = (over: Partial<ForecastDay> = {}): ForecastDay => ({
  date: '2026-10-26', high: 14, low: 7, sunrise: '07:31', sunset: '17:22', code: 61, rain_max: 70,
  hours: Array.from({ length: 24 }, (_, h) => ({ hour: h, temperature: h === 15 ? 14 : 8, rain_chance: h === 18 ? 70 : 5 })),
  ...over,
})

describe('the weather helpers', () => {
  it('words the sky from its code', () => {
    expect([0, 2, 3, 45, 61, 73, 95, null].map((c) => skyOf(c).word)).toEqual([
      'Clear', 'Partly cloudy', 'Cloudy', 'Fog', 'Rain', 'Snow', 'Thunder', 'Clear',
    ])
  })

  it('reads the radar stamp as UTC and times as hours', () => {
    expect(stampTime('202610261205').toISOString()).toBe('2026-10-26T12:05:00.000Z')
    expect(hoursOf('07:45')).toBe(7.75)
  })

  it('says the day in words', () => {
    expect(daySummary(day())).toBe('From 7° to 14°, warmest around 15:00; rain most likely around 18:00 (70%).')
    const dry = day({ hours: day().hours.map((h) => ({ ...h, rain_chance: 5 })) })
    expect(daySummary(dry)).toBe('From 7° to 14°, warmest around 15:00; little chance of rain.')
  })
})
