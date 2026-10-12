import { fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { AlertMessage, AlertRules, AlertSettings, Incident } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { sentBody, stubApi } from '../test/stubApi'

const SETTINGS: AlertSettings = {
  routing: { backup: 'nas', updates: 'nas', uptime: 'nas', rules: 'nas', portfolio: 'portfolio', manual: 'nas' },
  quiet: { enabled: true, start: '23:00', end: '07:00' },
  categories: { backup: 'Backups', updates: 'Container updates', uptime: 'Uptime Kuma', rules: 'Hub alert rules', portfolio: 'Portfolio', manual: 'Sent from the hub' },
  chats: [{ key: 'nas', label: 'NAS alerts', configured: true }, { key: 'portfolio', label: 'Portfolio', configured: true }],
  token_set: true,
  notify_key_set: true,
}

const msg = (id: number, over: Partial<AlertMessage>): AlertMessage => ({
  id, ts: '2026-10-01T10:00:00Z', source: 'backup', category: 'backup', severity: 'ok',
  title: 'NAS backup OK', body: '', chat: 'nas', status: 'sent', error: null, sent_at: '2026-10-01T10:00:00Z', ...over,
})

const MESSAGES = [
  msg(3, { source: 'rule.disk_space', category: 'rules', severity: 'warning', title: 'volume2 is 92% full', body: '500 GB left', status: 'held' }),
  msg(2, { source: 'bot', category: 'bot', severity: 'info', title: '/status from Pim' }),
  msg(1, { severity: 'error', title: 'Backup failed', status: 'failed', error: 'Telegram answered 403' }),
]

const RULES: AlertRules = {
  rules: {
    disk_space: { enabled: true, threshold_pct: 90 },
    smart: { enabled: true },
    portfolio_move: { enabled: false, threshold_pct: 3 },
  },
  labels: { disk_space: 'Disk space', smart: 'Disk SMART', portfolio_move: 'Portfolio move' },
}

const INCIDENTS: Incident[] = [
  { key: 'disk_space:volume2', rule: 'disk_space', severity: 'warning', title: 'volume2 is 92% full', body: '500 GB left', opened_at: '2026-10-01T09:00:00Z', last_seen_at: '2026-10-01T10:00:00Z', resolved_at: null },
  { key: 'smart:sdb', rule: 'smart', severity: 'warning', title: 'Disk sdb has SMART warnings', body: '', opened_at: '2026-09-30T09:00:00Z', last_seen_at: '2026-09-30T10:00:00Z', resolved_at: '2026-09-30T11:00:00Z' },
]

function setup(over: Record<string, unknown> = {}) {
  return stubApi({
    '/api/alerts/settings': SETTINGS,
    '/api/alerts/messages?limit=100': MESSAGES,
    '/api/alerts/messages?limit=100&category=rules': [MESSAGES[0]],
    '/api/alerts/rules': RULES,
    '/api/alerts/incidents': INCIDENTS,
    ...over,
  })
}

describe('AlertsPage', () => {
  it('shows the log with what happened to each message', async () => {
    setup()
    renderRoute('/alerts')

    const log = await screen.findByRole('region', { name: 'Messages' })
    expect(await within(log).findByText('volume2 is 92% full')).toBeInTheDocument()
    expect(within(log).getByText('Held for the morning digest')).toBeInTheDocument()
    expect(within(log).getByText(/Hub rule/)).toBeInTheDocument()
    expect(within(log).getByText('Sent to NAS alerts')).toBeInTheDocument()
    expect(within(log).getByText('Not sent: Telegram answered 403')).toBeInTheDocument()
  })

  it('filters the log by category', async () => {
    const fetchMock = setup()
    renderRoute('/alerts')

    fireEvent.click(await screen.findByRole('button', { name: 'Hub alert rules' }))

    expect(screen.getByRole('button', { name: 'Hub alert rules' })).toHaveAttribute('aria-pressed', 'true')
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/alerts/messages?limit=100&category=rules', expect.anything()),
    )
  })

  it('sends a message to the chosen chat', async () => {
    const fetchMock = setup({ 'POST /api/alerts/send': msg(9, { source: 'hub', category: 'manual', title: 'Hi' }) })
    renderRoute('/alerts')

    const form = await screen.findByRole('form', { name: 'Send a message' })
    fireEvent.change(within(form).getByLabelText('Message'), { target: { value: 'Hi\nfrom the hub' } })
    fireEvent.change(within(form).getByLabelText('To'), { target: { value: 'portfolio' } })
    fireEvent.submit(form)

    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'POST', '/api/alerts/send')).toEqual({ chat: 'portfolio', text: 'Hi\nfrom the hub' }),
    )
    await vi.waitFor(() => expect(within(form).getByLabelText('Message')).toHaveValue(''))
  })

  it('reports a message Telegram refused', async () => {
    setup({ 'POST /api/alerts/send': msg(9, { status: 'failed', error: 'No chat id set for nas' }) })
    renderRoute('/alerts')

    const form = await screen.findByRole('form', { name: 'Send a message' })
    fireEvent.change(within(form).getByLabelText('Message'), { target: { value: 'Hi' } })
    fireEvent.submit(form)

    expect(await within(form).findByRole('alert')).toHaveTextContent('Not sent: No chat id set for nas')
  })

  it('lists open alerts only', async () => {
    setup()
    renderRoute('/alerts')

    const open = await screen.findByRole('region', { name: 'Open alerts' })
    expect(await within(open).findByText('volume2 is 92% full')).toBeInTheDocument()
    expect(within(open).queryByText('Disk sdb has SMART warnings')).not.toBeInTheDocument()
    expect(within(open).getByText('1 open')).toBeInTheDocument()
    expect(screen.getAllByText('1 open')).toHaveLength(2) // the card and the page header
    // A warning card with a pulsing icon.
    expect(within(open).getAllByRole('listitem')[0].querySelector('.motion-safe\\:animate-halo')).not.toBeNull()
  })

  it('says all is quiet since the last alert ended, with the last seven days', async () => {
    const day = (n: number, h = 9) => new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate() - n, h).toISOString()
    setup({
      '/api/alerts/incidents': [
        { ...INCIDENTS[0], severity: 'error', opened_at: day(3), resolved_at: day(3, 11) },
        { ...INCIDENTS[1], opened_at: day(5), resolved_at: day(5, 10) },
      ],
    })
    renderRoute('/alerts')

    const card = await screen.findByRole('region', { name: 'Open alerts' })
    expect(await within(card).findByText('All quiet')).toBeInTheDocument()
    expect(within(card).getByText(/^Nothing has needed you for \d+ (h|days)$/)).toBeInTheDocument()
    const dots = within(within(card).getByRole('list', { name: 'The last 7 days' })).getAllByRole('listitem')
    expect(dots.map((d) => d.querySelector('b')?.getAttribute('data-worst'))).toEqual(['none', 'warning', 'none', 'error', 'none', 'none', 'none'])
    expect(screen.getByText('All quiet', { selector: '.uppercase' })).toBeInTheDocument()
  })

  it('puts open alerts before the messages, for a phone', async () => {
    setup()
    renderRoute('/alerts')
    const open = await screen.findByRole('region', { name: 'Open alerts' })
    const messages = screen.getByRole('region', { name: 'Messages' })
    expect(open.compareDocumentPosition(messages) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('edits and saves rules', async () => {
    const fetchMock = setup({ 'PUT /api/alerts/rules': RULES })
    renderRoute('/alerts')

    const rules = await screen.findByRole('region', { name: 'Hub rules' })
    const save = await within(rules).findByRole('button', { name: 'Save rules' })
    expect(save).toBeDisabled()

    fireEvent.click(within(rules).getByRole('switch', { name: 'Portfolio move on' }))
    fireEvent.change(within(rules).getByLabelText(/Any pool above/), { target: { value: '85' } })
    fireEvent.click(save)

    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', '/api/alerts/rules')).toEqual({
        disk_space: { enabled: true, threshold_pct: 85 },
        smart: { enabled: true },
        portfolio_move: { enabled: true, threshold_pct: 3 },
      }),
    )
    expect(await within(rules).findByText('Rules saved')).toBeInTheDocument()
  })

  it('changes quiet hours and routing', async () => {
    const fetchMock = setup({ 'PUT /api/alerts/settings': SETTINGS })
    renderRoute('/alerts')

    const delivery = await screen.findByRole('region', { name: 'Delivery' })
    fireEvent.change(within(delivery).getByLabelText('From'), { target: { value: '22:30' } })
    fireEvent.change(within(delivery).getByLabelText('Chat for Backups'), { target: { value: 'portfolio' } })
    fireEvent.click(within(delivery).getByRole('button', { name: 'Save' }))

    await vi.waitFor(() =>
      expect(sentBody(fetchMock, 'PUT', '/api/alerts/settings')).toMatchObject({
        quiet: { enabled: true, start: '22:30', end: '07:00' },
        routing: { backup: 'portfolio' },
      }),
    )
  })

  it('says what is missing from the setup', async () => {
    setup({ '/api/alerts/settings': { ...SETTINGS, token_set: false, chats: [{ key: 'nas', label: 'NAS alerts', configured: false }] } })
    renderRoute('/alerts')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Not set up yet: TELEGRAM_BOT_TOKEN, the chat id for NAS alerts.',
    )
  })
})
