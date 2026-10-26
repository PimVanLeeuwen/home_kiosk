import { fireEvent, screen, within } from '@testing-library/react'
import type { Forecast, ForecastDay } from '../lib/weatherTypes'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const inDays = (n: number) => iso(new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate() + n))

const day = (n: number, over: Partial<ForecastDay> = {}): ForecastDay => ({
  date: inDays(n), high: 12 + n, low: 5 + (n % 3), sunrise: '07:31', sunset: '17:22', code: n === 0 ? 61 : 3, rain_max: n === 0 ? 70 : 0,
  hours: Array.from({ length: 24 }, (_, h) => ({ hour: h, temperature: 6 + (h > 6 && h < 20 ? 6 : 0), rain_chance: h === 18 ? 70 : 0 })),
  ...over,
})
const FORECAST: Forecast = { as_of: new Date().toISOString(), stale: false, days: Array.from({ length: 7 }, (_, n) => day(n)) }
const radar = (wet: boolean) => ({ as_of: new Date().toISOString(), stale: false, stamp: '202610261205', wet, home: [281, 312] })

describe('WeatherPage', () => {
  it('shows today by the hour, the week as ranges, and no radar while dry', async () => {
    stubApi({ '/api/forecast': FORECAST, '/api/radar': radar(false) })
    renderRoute('/weather')

    expect(await screen.findByText('Dry for now')).toBeInTheDocument()
    const today = screen.getByRole('region', { name: 'Today' })
    expect(within(today).getByRole('img', { name: /From 5° to 12°.*rain most likely around 18:00 \(70%\)/ })).toBeInTheDocument()
    expect(today.querySelectorAll('[data-night]')).toHaveLength(2)
    expect(today.querySelector('[data-now]')).not.toBeNull()
    const week = screen.getByRole('region', { name: 'The week' })
    expect(within(week).getAllByRole('listitem')).toHaveLength(7)
    expect(within(week).getByRole('listitem', { name: /^Today: Rain, 5° to 12°, 70% chance of rain$/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Rain radar' })).toHaveTextContent('No rain expected in the next two hours')
  })

  it('shows the radar while rain is coming, and words when its picture is missing', async () => {
    stubApi({ '/api/forecast': FORECAST, '/api/radar': radar(true) })
    renderRoute('/weather')

    const card = await screen.findByRole('region', { name: 'Rain radar' })
    const picture = await within(card).findByRole('img', { name: /The rain radar round home at/ })
    expect(picture.getAttribute('src')).toBe('/api/radar/map?at=202610261205')
    fireEvent.error(picture)
    expect(card).toHaveTextContent('The radar is not available right now.')
  })

  it('says when the forecast is not available', async () => {
    stubApi({})
    renderRoute('/weather')

    expect(await within(screen.getByRole('region', { name: 'The week' })).findByText(/not available/i)).toBeInTheDocument()
  })
})
