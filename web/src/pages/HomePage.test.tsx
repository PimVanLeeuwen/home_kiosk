import { screen, within } from '@testing-library/react'
import { renderRoute } from '../test/renderRoute'
import { BACKUPS, PORTFOLIO, SERVICES, nasFixture } from '../test/fixtures'
import { ARTICLES, NEWS_GROUPS } from '../test/newsFixtures'
import { stubApi } from '../test/stubApi'

function setup(over: Record<string, unknown> = {}) {
  stubApi({
    '/api/nas': nasFixture(),
    '/api/services': SERVICES,
    '/api/portfolio': PORTFOLIO,
    '/api/news/articles?limit=5': { articles: ARTICLES, total: ARTICLES.length },
    '/api/news/groups': NEWS_GROUPS,
    ...over,
  })
  renderRoute('/')
}

const card = (name: string) => screen.getByRole('region', { name })

describe('HomePage', () => {
  it('greets and says all is well when nothing needs attention', async () => {
    setup()

    expect(await screen.findByText(/everything is running/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^Good (night|morning|afternoon|evening)$/)
    expect(document.title).toBe('Home · Home hub')
    expect(screen.getByText('37 / 37')).toBeInTheDocument()
    expect(screen.getByText('None')).toBeInTheDocument()
    // In the strip and in the Backups card.
    expect(screen.getAllByText(/^today 0?\d:31$/)).toHaveLength(2)
  })

  it('shows portfolio value, day change and the top three holdings', async () => {
    setup()

    const portfolio = await screen.findByRole('region', { name: 'Portfolio' })
    expect(await within(portfolio).findByText('€ 24.490')).toBeInTheDocument()
    expect(within(portfolio).getByText(/\+0,91% today/)).toBeInTheDocument()
    expect(within(portfolio).getAllByRole('row')).toHaveLength(3)
    expect(within(portfolio).getByRole('img', { name: /last 30 days/ })).toBeInTheDocument()
  })

  it('shows NAS meters and the fullest pools', async () => {
    setup()

    const nas = await screen.findByRole('region', { name: 'NAS' })
    expect(await within(nas).findByRole('meter', { name: 'CPU' })).toHaveAttribute('aria-valuenow', '11')
    expect(within(nas).getByRole('meter', { name: 'volume3' })).toBeInTheDocument()
    expect(within(nas).getByText(/19,2 Mbit\/s/)).toBeInTheDocument()
  })

  it('lists the newest headlines, each opening in the reader', async () => {
    setup()

    const news = await screen.findByRole('region', { name: 'Latest news' })
    const links = await within(news).findAllByRole('link', { name: /Miljoenennota|Jellyfin|Old story/ })
    expect(links.map((l) => l.textContent)).toEqual([
      expect.stringContaining('Kabinet presenteert Miljoenennota'),
      expect.stringContaining('Jellyfin 12.1 lands'),
      expect.stringContaining('Old story'),
    ])
    expect(links[0]).toHaveAttribute('href', '/news?a=a1')
    expect(links[0]).toHaveTextContent('unread')
    expect(links[2]).not.toHaveTextContent('unread')
    expect(await within(news).findByText(/NOS · Nederland/)).toBeInTheDocument()
  })

  it('shows the last backup and service tiles with stats', async () => {
    setup()

    expect(await within(card('Backups')).findByText('Succeeded')).toBeInTheDocument()
    const services = card('Services')
    expect(await within(services).findByRole('link', { name: /Jellyfin/ })).toHaveTextContent('1 streaming')
  })

  it('shows the latest run per volume once there is run history', async () => {
    setup({ '/api/backups': BACKUPS })

    const card = await screen.findByRole('region', { name: 'Backups' })
    expect(await within(card).findByText('Failed')).toBeInTheDocument()
    expect(within(card).getByText(/OK · 4 min · 2,5 GB/)).toBeInTheDocument()
    expect(within(card).getByText(/Failed · 19 min/)).toBeInTheDocument()
    expect(within(card).getByText(/Next run due/)).toBeInTheDocument()
  })

  it('raises what needs a look in the strip and the subtitle', async () => {
    setup({
      '/api/nas': nasFixture({
        storage: {
          used_pct: 70,
          pools: [{ name: 'volume2', used_bytes: 5.9e12, total_bytes: 6e12, used_pct: 98.5, free_bytes: 8.7e10 }],
        },
      }),
    })

    expect(await screen.findByText(/1 thing needs a look/)).toBeInTheDocument()
    expect(screen.getByText('volume2 98% full')).toBeInTheDocument()
    expect(screen.getByText('Needs a look')).toBeInTheDocument()
    expect(within(card('NAS')).getByRole('meter', { name: 'volume2' })).toBeInTheDocument()
  })

  it('shows the weather with a rain summary and chart, and names Buienradar', async () => {
    const at = (minute: number) => new Date(2026, 9, 9, 15, minute).toISOString()
    setup({
      '/api/weather': {
        as_of: at(0), stale: false, station: 'Meetstation De Bilt', measured_at: at(0),
        description: 'Zwaar bewolkt', temperature: 12.9, feel_temperature: 10.6, wind_bft: 4,
        wind_direction: 'ZW', humidity: 94, rain_last_hour: 0, sunrise: at(0), sunset: new Date(2026, 9, 9, 18, 57).toISOString(),
        rain: [0, 0, 0.6, 1.4, 0].map((mm, i) => ({ at: at(i * 5), mm_per_hour: mm })),
      },
    })

    const weather = await screen.findByRole('region', { name: 'Weather' })
    expect(within(weather).getByText('13 °C')).toBeInTheDocument()
    expect(within(weather).getByText('Zwaar bewolkt')).toBeInTheDocument()
    expect(within(weather).getByText('Feels like 11 °C · Wind 4 Bft ZW · Humidity 94%')).toBeInTheDocument()
    expect(within(weather).getByRole('img', { name: 'Rain from 15:10, up to 1,4 mm/h' })).toBeInTheDocument()
    expect(within(weather).getByRole('link', { name: 'Buienradar' })).toHaveAttribute('href', 'https://www.buienradar.nl')
    expect(weather).toHaveTextContent('Sunset 18:57')
    expect(weather).toHaveTextContent(', De Bilt')
  })

  it('keeps the other cards when one source is down', async () => {
    setup({ '/api/portfolio': new Error('offline') })

    expect(await within(card('Portfolio')).findByText('The portfolio is not available right now.')).toBeInTheDocument()
    expect(await within(card('NAS')).findByRole('meter', { name: 'CPU' })).toBeInTheDocument()
  })
})
