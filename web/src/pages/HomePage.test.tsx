import { screen, within } from '@testing-library/react'
import { renderRoute } from '../test/renderRoute'
import { PORTFOLIO, SERVICES, nasFixture } from '../test/fixtures'
import { ARTICLES, NEWS_GROUPS } from '../test/newsFixtures'
import { stubApi } from '../test/stubApi'

function setup(over: Record<string, unknown> = {}) {
  stubApi({
    '/api/nas': nasFixture(),
    '/api/services': SERVICES,
    '/api/portfolio': PORTFOLIO,
    '/api/news/articles?limit=5': { articles: ARTICLES, total: ARTICLES.length },
    '/api/news/groups': NEWS_GROUPS,
    '/api/alerts/incidents': [],
    ...over,
  })
  renderRoute('/')
}

const card = (name: string) => screen.getByRole('region', { name })
const incident = (rule: string, severity: 'info' | 'warning' | 'error', title: string, body = '') => ({
  key: `${rule}:x`, rule, severity, title, body, opened_at: '2026-11-20T09:00:00Z', last_seen_at: '2026-11-21T08:00:00Z', resolved_at: null,
})

describe('HomePage', () => {
  it('greets, says the house is quiet and folds the healthy house cards into one line', async () => {
    setup()

    const heading = screen.getByRole('heading', { level: 1 })
    expect(await within(heading).findByText(/The house is quiet\./)).toBeInTheDocument()
    expect(heading).toHaveTextContent(/^Good (night|morning|afternoon|evening)\./)
    expect(document.title).toBe('Home · Home hub')
    expect(screen.queryByRole('list', { name: 'Needs a look' })).not.toBeInTheDocument()
    // The house cards with nothing to report are one sentence that leads to House, not cards.
    const healthy = await screen.findByText(/^The NAS is healthy, \d+ of \d+ services up, last backup today 0?\d:31/)
    expect(healthy.parentElement!.querySelector('a')).toHaveAttribute('href', '/house')
    expect(screen.queryByRole('region', { name: 'Backups' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'NAS' })).not.toBeInTheDocument()
  })

  it('raises each open incident as a row, errors first, with the way to its page', async () => {
    setup({
      '/api/alerts/incidents': [
        incident('outside_services', 'warning', 'TransIP: TransNOC reports a problem', 'Degraded on their status page.'),
        incident('backup_missing', 'error', 'No good dump of the Tracearr database'),
        incident('portfolio_move', 'info', 'Portfolio moved'),
        { ...incident('smart', 'error', 'Disk sdb is failing'), resolved_at: '2026-11-21T07:00:00Z' },
      ],
    })

    expect(await screen.findByText(/2 things need a look\./)).toBeInTheDocument()
    const rows = within(screen.getByRole('list', { name: 'Needs a look' })).getAllByRole('listitem')
    expect(rows.map((r) => r.querySelector('p')!.textContent)).toEqual(['No good dump of the Tracearr database', 'TransIP: TransNOC reports a problem'])
    expect(within(rows[0]).getByRole('link', { name: 'Backups' })).toHaveAttribute('href', '/house/backups')
    expect(within(rows[1]).getByRole('link', { name: 'Services' })).toHaveAttribute('href', '/house/services')
    expect(rows[1]).toHaveTextContent(/Degraded on their status page\. · since Fri 20 Nov/)
  })

  it('leaves the link out of a row about Today itself', async () => {
    setup({ '/api/alerts/incidents': [incident('train', 'warning', 'Your 07:16 train is cancelled')] })

    const row = await screen.findByText('Your 07:16 train is cancelled')
    expect(row.closest('li')!.querySelector('a')).toBeNull()
  })

  it('shows portfolio value, day change and the top three holdings', async () => {
    setup()

    const portfolio = await screen.findByRole('region', { name: 'Portfolio' })
    expect(await within(portfolio).findByText('€ 24.490')).toBeInTheDocument()
    expect(within(portfolio).getByText(/\+0,91% today/)).toBeInTheDocument()
    expect(within(portfolio).getAllByRole('row')).toHaveLength(3)
    expect(within(portfolio).getByRole('img', { name: /last 30 days/ })).toBeInTheDocument()
    // Today in a pill, the month beside today's amount, and the period's high under the chart.
    expect(within(portfolio).getByText('+0,91% today')).toHaveClass('text-up')
    expect(within(portfolio).getByText('· +2,04% in 30 days')).toHaveClass('text-up')
    expect(within(portfolio).getByText('High € 24.490 · 30 Sept')).toBeInTheDocument()
    expect(within(portfolio).getByText('VWRL')).toBeInTheDocument()
  })

  it('draws a falling month in red', async () => {
    setup({
      '/api/portfolio': {
        ...PORTFOLIO,
        history: [
          { d: '2026-09-28', v: 25714 },
          { d: '2026-09-29', v: 25000 },
          { d: '2026-09-30', v: 24490 },
        ],
      },
    })

    const portfolio = await screen.findByRole('region', { name: 'Portfolio' })
    expect(await within(portfolio).findByText('· −4,76% in 30 days')).toHaveClass('text-down')
    expect(within(portfolio).getByText('High € 25.714 · 28 Sept')).toBeInTheDocument()
    const line = within(portfolio).getByRole('img', { name: /last 30 days/ }).querySelector('polyline')
    expect(line).toHaveAttribute('stroke', 'var(--color-down)')
  })


  it('flags a short runway and a failing disk in the NAS card', async () => {
    setup({
      '/api/nas': nasFixture({
        storage: { used_pct: 80, pools: [{ name: 'volume2', used_bytes: 5.5e12, total_bytes: 6e12, used_pct: 91.7, free_bytes: 5e11, projection_months: 1.4 }] },
        disks: [{ name: 'sda', temp_c: 35, smart: 'ok' }, { name: 'sdb', temp_c: 41, smart: 'fail' }],
      }),
    })

    // A failing disk lifts the NAS card to the top, so look it up once it is there.
    expect(await screen.findByText('Full in about 1 month')).toHaveClass('text-warn')
    const nas = screen.getByRole('region', { name: 'NAS' })
    expect(within(nas).queryByText('Needs a look')).not.toBeInTheDocument()
    expect(within(nas).getByText('1 of 2')).toBeInTheDocument()
    expect(within(nas).getByRole('img', { name: 'sdb: failing' })).toBeInTheDocument()
    expect(within(nas).getByText('Disks · 41 °C')).toBeInTheDocument()
    // No UPS answering: the line leaves it out.
    expect(within(nas).queryByText(/UPS/)).not.toBeInTheDocument()
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
    expect(links[0]).toHaveAttribute('href', '/read/news?a=a1')
    expect(links[0]).toHaveTextContent('unread')
    expect(links[2]).not.toHaveTextContent('unread')
    // The group is a chip in its own colour before the source; the newest story leads.
    const chip = await within(news).findByText('Nederland')
    expect(chip).toHaveStyle({ color: '#b4aaff' })
    expect(within(news).getAllByText('Tech')[0]).toHaveStyle({ color: '#8cc4ff' })
    expect(within(news).getByText(/^NOS · /)).toBeInTheDocument()
    expect(within(news).getByText(/Kabinet presenteert Miljoenennota/)).toHaveClass('text-title')
    expect(within(news).getByText(/Jellyfin 12.1 lands/)).not.toHaveClass('text-title')
    expect(within(news).getByText('2 unread')).toBeInTheDocument()
  })

  it('leaves the unread pill out when everything is read', async () => {
    setup({ '/api/news/groups': NEWS_GROUPS.map((g) => ({ ...g, unread: 0 })) })

    const news = await screen.findByRole('region', { name: 'Latest news' })
    await within(news).findByText('Nederland')
    expect(within(news).queryByText(/^\d+ unread$/)).not.toBeInTheDocument()
  })






  it('unfolds a house card with a problem into a cell, out of the healthy line', async () => {
    setup({
      '/api/nas': nasFixture({
        storage: {
          used_pct: 70,
          pools: [{ name: 'volume2', used_bytes: 5.9e12, total_bytes: 6e12, used_pct: 98.5, free_bytes: 8.7e10 }],
        },
      }),
    })

    const nas = await screen.findByRole('region', { name: 'NAS' })
    expect(nas).toHaveAttribute('data-cell', 'true')
    expect(within(nas).getByRole('meter', { name: 'volume2' })).toBeInTheDocument()
    expect(await screen.findByText(/services up/)).not.toHaveTextContent(/NAS/)
  })

  it('lights the top of the page in the colour of the time of day', async () => {
    setup()

    await screen.findByText(/The house is quiet/)
    expect(screen.getByTestId('sky').style.getPropertyValue('--sky')).toMatch(/^rgb\(/)
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
    // The temperature sits inside the rain ring, now at the top.
    const ring = within(weather).getByRole('img', { name: 'Rain from 15:10, up to 1,4 mm/h' })
    expect(ring).toHaveTextContent('13°')
    expect(ring.querySelectorAll('[data-wet]')).toHaveLength(2)
    expect(within(weather).getByText('Rain from 15:10, up to 1,4 mm/h')).toBeInTheDocument()
    expect(within(weather).getByText('Zwaar bewolkt')).toBeInTheDocument()
    expect(within(weather).getByText('Feels like 11 °C · Wind 4 Bft ZW · Humidity 94%')).toBeInTheDocument()
    expect(within(weather).getByRole('img', { name: 'Rain from 15:10, up to 1,4 mm/h' })).toBeInTheDocument()
    expect(within(weather).getByRole('link', { name: 'Buienradar' })).toHaveAttribute('href', 'https://www.buienradar.nl')
    expect(weather).toHaveTextContent('Sunrise 15:00 · Sunset 18:57')
    expect(weather).toHaveTextContent(', De Bilt')
  })

  it('keeps the other cards when one source is down', async () => {
    setup({ '/api/portfolio': new Error('offline') })

    expect(await within(card('Portfolio')).findByText('The portfolio is not available right now.')).toBeInTheDocument()
    expect(await screen.findByText(/^The NAS is healthy/)).toBeInTheDocument()
  })

  it('lays the cards out as cells, the wide ones over two columns', async () => {
    setup()

    const news = await screen.findByRole('region', { name: 'Latest news' })
    expect(news).toHaveAttribute('data-cell', 'true')
    expect(news.closest('[data-card]')).toHaveClass('sm:col-span-2')
    expect(screen.getByRole('region', { name: "The day's cards" })).toHaveClass('grid-flow-row-dense')
  })

  it('puts a failed backup first and running laundry before the calm cards', async () => {
    const machine = {
      id: 'w', name: 'Washing machine', kind: 'washer', state: 'running', online: true, door_open: false, error: null,
      done_at: null, program: 'Cotton', remaining_minutes: 38, total_minutes: 95, ready_at: null,
    }
    setup({
      '/api/nas': nasFixture({ backup: { status: 'fail', at: new Date().toISOString() } }),
      '/api/laundry': { as_of: new Date().toISOString(), stale: false, showing: true, machines: [machine] },
    })

    await screen.findByRole('region', { name: 'Laundry' })
    const regions = screen.getAllByRole('region').map((r) => r.getAttribute('aria-labelledby')).filter(Boolean)
    expect(regions[0]).toBe('card-backups')
    // The failed backup is the hero, in its own frame and light, across the full width.
    expect(screen.getByRole('region', { name: 'Backups' }).closest('[data-hero]')).not.toBeNull()
    expect(screen.getByRole('region', { name: 'Backups' }).closest('[data-card]')).toHaveClass('col-span-full')
    expect(screen.getByRole('region', { name: 'Laundry' }).parentElement!.querySelector('[data-live="accent"]')).not.toBeNull()
    expect(regions.indexOf('card-laundry')).toBeLessThan(regions.indexOf('card-latest-news'))
  })
})
