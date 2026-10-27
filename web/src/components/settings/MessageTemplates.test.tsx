import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { MessageTemplate } from '../../lib/types'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { MessageTemplates } from './MessageTemplates'
import { TelegramText } from './TelegramText'

const tpl = (id: string, over: Partial<MessageTemplate> = {}): MessageTemplate => ({
  id,
  group: 'Alert rules',
  label: id,
  description: `${id} description`,
  parent: null,
  category: 'Hub alert rules',
  placeholders: [
    { name: 'level', description: 'The severity', block: false },
    { name: 'pool', description: 'Pool name', block: false },
  ],
  default: '<b>{level}</b> · <b>{pool} is full</b>',
  text: '<b>{level}</b> · <b>{pool} is full</b>',
  customised: false,
  preview: '<b>WARNING</b> · <b>volume2 is full</b>',
  ...over,
})

const LIST = [
  tpl('Disk space'),
  tpl('Portfolio report', { group: 'Reports', category: 'Portfolio', id: 'portfolio_report' }),
  tpl('Holding line', { group: 'Reports', parent: 'portfolio_report', category: null, customised: true, text: '{pool}!' }),
]
const DISK = '/api/alerts/templates/Disk space'

/** Renders the list and opens every group, as they start folded. */
async function setup(extra: Record<string, unknown> = {}) {
  const fetchMock = stubApi({
    '/api/alerts/templates': LIST,
    [`POST ${DISK}/preview`]: (body: { text: string }) => ({
      html: body.text.replace('{pool}', 'volume2').replace('{level}', 'WARNING'),
      error: body.text.includes('{nope}') ? 'Unknown placeholder: {nope}.' : null,
    }),
    ...extra,
  })
  render(
    <MemoryRouter>
      <MessageTemplates />
    </MemoryRouter>,
  )
  for (const fold of await screen.findAllByRole('button', { expanded: false })) fireEvent.click(fold)
  return fetchMock
}

const editor = () => screen.getByRole('form', { name: 'Edit Disk space' })
const textarea = () => within(editor()).getByRole('textbox', { name: 'Message text' })

describe('MessageTemplates', () => {
  it('folds each group, showing how many messages it holds and how many are changed', async () => {
    stubApi({ '/api/alerts/templates': LIST })
    render(
      <MemoryRouter>
        <MessageTemplates />
      </MemoryRouter>,
    )
    const fold = await screen.findByRole('button', { name: /Reports/ })
    expect(fold).toHaveAttribute('aria-expanded', 'false')
    expect(fold).toHaveTextContent('2 messages, 1 customised')
    expect(screen.getByRole('button', { name: /Alert rules/ })).toHaveTextContent('1 message')
    expect(screen.queryByRole('button', { name: 'Edit Portfolio report' })).not.toBeInTheDocument()

    fireEvent.click(fold)
    expect(fold).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Edit Portfolio report' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit Disk space' })).not.toBeInTheDocument()

    fireEvent.click(fold)
    expect(screen.queryByRole('button', { name: 'Edit Portfolio report' })).not.toBeInTheDocument()
  })

  it('lists the messages by group, marks changed ones and links to Alerts', async () => {
    await setup()
    const reports = await screen.findByRole('region', { name: 'Reports' })
    expect(within(reports).getByText('Customised')).toBeInTheDocument()
    expect(within(reports).getByText(/routed as Portfolio/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Alert rules' })).toHaveTextContent('Disk space description')
    expect(screen.getByRole('link', { name: 'Alerts page' })).toHaveAttribute('href', '/alerts')
  })

  it('edits with clickable placeholders and a live preview, then saves', async () => {
    const fetchMock = await setup({ [`PUT ${DISK}`]: (body: { text: string }) => tpl('Disk space', { text: body.text, customised: true }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))

    fireEvent.change(textarea(), { target: { value: 'Pool ' } })
    fireEvent.click(within(editor()).getByRole('button', { name: '{pool}: Pool name' }))
    expect(textarea()).toHaveValue('Pool {pool}')
    await waitFor(() => expect(within(editor()).getByRole('figure', { name: 'Preview' })).toHaveTextContent('Pool volume2'), {
      timeout: 2000,
    })

    fireEvent.click(within(editor()).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Customised')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', DISK)).toEqual({ text: 'Pool {pool}' })
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
  })

  it('shows template errors and blocks saving', async () => {
    await setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))
    fireEvent.change(textarea(), { target: { value: '{nope}' } })

    expect(await within(editor()).findByRole('alert', {}, { timeout: 2000 })).toHaveTextContent('Unknown placeholder: {nope}.')
    expect(within(editor()).getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(within(editor()).getByRole('button', { name: 'Send test' })).toBeDisabled()
  })

  it('sends a test and says when Telegram refused it', async () => {
    let status = 'sent'
    await setup({ [`POST ${DISK}/test`]: () => ({ status, error: status === 'failed' ? 'No chat id set for nas' : null }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))

    fireEvent.click(within(editor()).getByRole('button', { name: 'Send test' }))
    expect(await within(editor()).findByRole('status')).toHaveTextContent('Test sent to Telegram')

    status = 'failed'
    fireEvent.click(within(editor()).getByRole('button', { name: 'Send test' }))
    expect(await within(editor()).findByText('Not sent: No chat id set for nas.')).toBeInTheDocument()
  })

  it('resets a changed message to the built-in text', async () => {
    const HOLDING = '/api/alerts/templates/Holding line'
    await setup({
      [`POST ${HOLDING}/preview`]: { html: 'x', error: null },
      [`DELETE ${HOLDING}`]: tpl('Holding line', { group: 'Reports', parent: 'portfolio_report', category: null }),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Holding line' }))
    const form = screen.getByRole('form', { name: 'Edit Holding line' })
    expect(within(form).getByText(/inside the portfolio report/)).toBeInTheDocument()

    fireEvent.click(within(form).getByRole('button', { name: 'Reset to default' }))
    expect(await within(form).findByRole('status')).toHaveTextContent('Back to the built-in text.')
    expect(within(form).getByRole('textbox', { name: 'Message text' })).toHaveValue('<b>{level}</b> · <b>{pool} is full</b>')
    expect(screen.queryByText('Customised')).not.toBeInTheDocument()
  })

  it('shows save errors from the hub', async () => {
    await setup({ [`PUT ${DISK}`]: failWith(422, { detail: '<b> is never closed.' }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))
    fireEvent.click(within(editor()).getByRole('button', { name: 'Save' }))
    expect(await within(editor()).findByText('<b> is never closed.')).toBeInTheDocument()
  })

  it('explains when the list is not available', async () => {
    stubApi({})
    render(
      <MemoryRouter>
        <MessageTemplates />
      </MemoryRouter>,
    )
    expect(await screen.findByText('The messages are not available right now.')).toBeInTheDocument()
  })
})

describe('TelegramText', () => {
  it('renders the allowed tags and entities, never raw HTML', () => {
    const { container } = render(<TelegramText html={'ERROR <b>Disk &lt;sdb&gt;</b> <i>a &amp; b</i> <code>x</code>'} />)
    expect(container.querySelector('strong')).toHaveTextContent('Disk <sdb>')
    expect(container.querySelector('em')).toHaveTextContent('a & b')
    expect(container.querySelector('code')).toHaveTextContent('x')
    expect(container.querySelector('script')).toBeNull()
  })

  it('renders an expandable quote open, as a quote', () => {
    const { container } = render(<TelegramText html={'<b>Markets</b>\n<blockquote expandable><b>NVDA</b> +2,10%</blockquote>'} />)
    const quote = container.querySelector('blockquote')
    expect(quote?.textContent).toBe('NVDA +2,10%')
    expect(quote?.querySelector('strong')?.textContent).toBe('NVDA')
    expect(container.textContent).not.toContain('expandable')
  })

  it('renders a link to a web address, and none to anything else', () => {
    const { container } = render(
      <TelegramText html={'<a href="https://nos.nl/a?x=1&amp;y=2">Kabinet</a> <a href="javascript:alert(1)">Bad</a>'} />,
    )
    const [good, bad] = container.querySelectorAll('a')
    expect(good).toHaveAttribute('href', 'https://nos.nl/a?x=1&y=2')
    expect(good).toHaveAttribute('rel', 'noreferrer')
    expect(good).toHaveTextContent('Kabinet')
    expect(bad).not.toHaveAttribute('href')
  })

  it('adds no empty line after a quote, which is a block already', () => {
    const { container } = render(<TelegramText html={'<blockquote>a</blockquote>\n\n<b>House</b>'} />)
    expect(container.textContent).toBe('a\nHouse')
  })

  it('renders a pre block as a monospace table that keeps its spacing', () => {
    const { container } = render(<TelegramText html={'<b>Report</b>\n<pre>VWRL  +1,12%\nAEX   −0,40%</pre>'} />)
    const pre = container.querySelector('pre')
    expect(pre?.textContent).toBe('VWRL  +1,12%\nAEX   −0,40%')
    expect(pre).toHaveClass('font-mono', 'whitespace-pre')
  })

  it('keeps the text of an unclosed tag', () => {
    const { container } = render(<TelegramText html="<b>half" />)
    expect(container).toHaveTextContent('half')
  })
})
