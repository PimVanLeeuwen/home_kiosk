import { screen, within } from '@testing-library/react'
import { nasFixture } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

const recent = (minutesAgo: number) => new Date(Date.now() - minutesAgo * 60_000).toISOString()
const message = (id: number, category: string, severity: string, title: string, ts = recent(30)) => ({
  id, ts, source: 'rule.x', category, severity, title, body: '', chat: 'nas', status: 'sent', error: null, sent_at: ts,
})

function setup(over: Record<string, unknown> = {}) {
  stubApi({
    '/api/nas': nasFixture(),
    '/api/alerts/incidents': [],
    '/api/alerts/messages?limit=40': [
      message(3, 'rules', 'error', 'No good dump of the Tracearr database'),
      message(2, 'portfolio', 'info', 'Evening report'),
      message(1, 'backup', 'ok', 'NAS backup OK', recent(26 * 60)),
    ],
    ...over,
  })
  renderRoute('/house')
}

describe('HouseOverviewPage', () => {
  it('opens House: all quiet, the vital signs as cells and the last 24 hours of the house', async () => {
    setup()

    expect(await screen.findByRole('heading', { level: 1, name: 'House' })).toBeInTheDocument()
    expect(screen.getByText('All running')).toBeInTheDocument()
    expect(await screen.findByText(/^All quiet: \d+ disks healthy, \d+ of \d+ containers running/)).toBeInTheDocument()
    const cells = screen.getByRole('region', { name: 'The house at a glance' })
    for (const name of ['CPU', 'Memory', 'Containers', 'Network']) expect(within(cells).getByRole('group', { name })).toBeInTheDocument()
    expect(within(cells).getByRole('link', { name: 'Docker →' })).toHaveAttribute('href', '/house/docker')

    // The house's own messages from the last day, not the portfolio's, each to its page.
    const day = within(cells).getByRole('group', { name: 'Last 24 hours' })
    expect(await within(day).findByRole('link', { name: /No good dump/ })).toHaveAttribute('href', '/house/alerts/3')
    expect(within(day).queryByText('Evening report')).toBeNull()
    expect(within(day).queryByText('NAS backup OK')).toBeNull()
  })

  it('leads with the house incidents only, each with the way to its page', async () => {
    const incident = (rule: string, severity: string, title: string) => ({
      key: rule, rule, severity, title, body: '', opened_at: '2026-11-20T09:00:00Z', last_seen_at: '', resolved_at: null,
    })
    setup({
      '/api/alerts/incidents': [
        incident('container_health', 'error', 'tracearr is down'),
        incident('train', 'warning', 'Your train is cancelled'),
      ],
    })

    const rows = await screen.findByRole('list', { name: 'Needs a look' })
    expect(within(rows).getAllByRole('listitem')).toHaveLength(1)
    expect(within(rows).getByRole('link', { name: 'Docker' })).toHaveAttribute('href', '/house/docker')
    expect(screen.getByText('1 to look at')).toBeInTheDocument()
    expect(await screen.findByText(/^The rest is fine: /)).toBeInTheDocument()
  })

  it('is the first House tab, current only on its own address', async () => {
    setup()

    const tabs = await screen.findByRole('navigation', { name: 'House pages' })
    expect(within(tabs).getAllByRole('link')[0]).toHaveTextContent('Overview')
    expect(within(tabs).getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
  })
})
