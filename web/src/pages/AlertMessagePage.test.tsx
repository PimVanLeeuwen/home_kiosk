import { fireEvent, screen, within } from '@testing-library/react'
import type { MessagePage, ServicesResponse } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const NOW = Date.now()
const ago = (min: number) => new Date(NOW - min * 60_000).toISOString()

const PAGE: MessagePage = {
  id: 7, ts: ago(30), source: 'rule.container_health', category: 'rules', severity: 'error',
  title: 'sonarr is down', body: 'Exit code 137.', chat: 'nas', status: 'sent', error: null,
  sent_at: ago(30), channel: 'ntfy', ntfy_id: 'n1', incident: 'down:sonarr', expired: false,
  expires_at: new Date(NOW + 7 * 86_400_000).toISOString(),
  html: '<b>ERROR</b> · <b>sonarr is down</b>\nExit code <code>137</code>.',
  state: { open: true, opened_at: ago(32), resolved_at: null },
  earlier: [
    { id: 7, ts: ago(30), severity: 'error', title: 'sonarr is down' },
    { id: 3, ts: ago(3000), severity: 'ok', title: 'Resolved: sonarr is down' },
  ],
  links: [
    { label: 'Logs in Dozzle', service: 'dozzle', path: '/show?name=sonarr', hint: 'sonarr' },
    { label: 'Docker page', page: '/docker', hint: '' },
  ],
  explanation: null,
  can_explain: true,
}

const SERVICES: ServicesResponse = {
  as_of: null, stale: false,
  groups: [{ name: 'Monitoring', services: [
    { id: 'dozzle', name: 'Dozzle', group: 'Monitoring', description: '', port: 8081, path: '/', container: 'dozzle', widget: null, status: 'up' } as ServicesResponse['groups'][0]['services'][0],
  ] }],
}

function setup(page: unknown = PAGE, extra: Record<string, unknown> = {}) {
  return stubApi({ '/api/alerts/messages/7': page, '/api/services': SERVICES, ...extra })
}

describe('AlertMessagePage', () => {
  it('shows the message, its state, the way onward and what came before', async () => {
    setup()
    renderRoute('/alerts/7')

    expect(await screen.findByRole('heading', { name: 'sonarr is down' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Still open')
    expect(screen.getByRole('status')).toHaveTextContent('for 32 min')
    expect(screen.getByText('137')).toHaveClass('font-mono')
    expect(screen.getByText('Hub rule')).toBeInTheDocument()
    const onward = screen.getByRole('navigation', { name: 'Go to' })
    expect(await within(onward).findByRole('link', { name: /Logs in Dozzle/ })).toHaveAttribute('href', 'http://localhost:8081/show?name=sonarr')
    expect(within(onward).getByRole('link', { name: 'Docker page' })).toHaveAttribute('href', '/docker')
    const earlier = screen.getByRole('region', { name: 'Earlier' })
    expect(within(earlier).getByRole('link', { name: 'Resolved: sonarr is down' })).toHaveAttribute('href', '/alerts/3')
    expect(within(earlier).getByText(/this message/)).toBeInTheDocument()
    expect(screen.getAllByText(/Sent to your phone \(ntfy\)/).length).toBeGreaterThan(0)
  })

  it('says when a problem was resolved', async () => {
    setup({ ...PAGE, state: { open: false, opened_at: ago(150), resolved_at: ago(30) } })
    renderRoute('/alerts/7')

    await screen.findByRole('heading', { name: 'sonarr is down' })
    expect(screen.getByRole('status')).toHaveTextContent('after 2 h 0 min')
    expect(screen.getByRole('status')).toHaveTextContent(/^Resolved at/)
  })

  it('asks Claude once and shows the answer', async () => {
    const answer = { cause: 'Killed for memory.', todo: 'Start it again.', asked_at: ago(0) }
    const fetchMock = setup(PAGE, { 'POST /api/alerts/messages/7/explain': answer })
    renderRoute('/alerts/7')

    fireEvent.click(await screen.findByRole('button', { name: 'Explain' }))

    const card = await screen.findByRole('region', { name: 'Explained' })
    expect(card).toHaveTextContent('Killed for memory.')
    expect(card).toHaveTextContent('Start it again.')
    expect(sentBody(fetchMock, 'POST', '/api/alerts/messages/7/explain')).toEqual({})
    expect(screen.queryByRole('button', { name: 'Explain' })).toBeNull()
  })

  it('says why Claude gave no answer', async () => {
    setup(PAGE, { 'POST /api/alerts/messages/7/explain': failWith(409, { detail: 'Claude did not answer.' }) })
    renderRoute('/alerts/7')

    fireEvent.click(await screen.findByRole('button', { name: 'Explain' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Claude did not answer.')
  })

  it('shows a kept explanation, and no button for a message that is not a problem', async () => {
    setup({ ...PAGE, severity: 'info', state: null, can_explain: false, links: [], earlier: [], explanation: null })
    renderRoute('/alerts/7')

    expect(await screen.findByRole('heading', { name: 'sonarr is down' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Explain' })).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Go to' })).toBeNull()
  })

  it('says a message has expired after 7 days', async () => {
    setup({ id: 7, ts: ago(8 * 1440), expired: true })
    renderRoute('/alerts/7')

    expect(await screen.findByRole('heading', { name: 'This message has expired' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open Alerts' })).toHaveAttribute('href', '/alerts')
  })

  it('says there is no such message', async () => {
    setup(failWith(404, { detail: 'No such message.' }))
    renderRoute('/alerts/7')

    expect(await screen.findByRole('heading', { name: 'No such message' })).toBeInTheDocument()
  })
})
