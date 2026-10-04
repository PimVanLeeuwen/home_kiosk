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
    { name: 'icon', description: 'The severity emoji', block: false },
    { name: 'pool', description: 'Pool name', block: false },
  ],
  default: '{icon} <b>{pool} is full</b>',
  text: '{icon} <b>{pool} is full</b>',
  customised: false,
  preview: '⚠️ <b>volume2 is full</b>',
  ...over,
})

const LIST = [
  tpl('Disk space'),
  tpl('Portfolio report', { group: 'Reports', category: 'Portfolio', id: 'portfolio_report' }),
  tpl('Holding line', { group: 'Reports', parent: 'portfolio_report', category: null, customised: true, text: '{pool}!' }),
]
const DISK = '/api/alerts/templates/Disk space'

function setup(extra: Record<string, unknown> = {}) {
  const fetchMock = stubApi({
    '/api/alerts/templates': LIST,
    [`POST ${DISK}/preview`]: (body: { text: string }) => ({
      html: body.text.replace('{pool}', 'volume2').replace('{icon}', '⚠️'),
      error: body.text.includes('{nope}') ? 'Unknown placeholder: {nope}.' : null,
    }),
    ...extra,
  })
  render(
    <MemoryRouter>
      <MessageTemplates />
    </MemoryRouter>,
  )
  return fetchMock
}

const editor = () => screen.getByRole('form', { name: 'Edit Disk space' })
const textarea = () => within(editor()).getByRole('textbox', { name: 'Message text' })

describe('MessageTemplates', () => {
  it('lists the messages by group, marks changed ones and links to Alerts', async () => {
    setup()
    const reports = await screen.findByRole('region', { name: 'Reports' })
    expect(within(reports).getByText('Customised')).toBeInTheDocument()
    expect(within(reports).getByText(/routed as Portfolio/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Alert rules' })).toHaveTextContent('Disk space description')
    expect(screen.getByRole('link', { name: 'Alerts page' })).toHaveAttribute('href', '/alerts')
  })

  it('edits with clickable placeholders and a live preview, then saves', async () => {
    const fetchMock = setup({ [`PUT ${DISK}`]: (body: { text: string }) => tpl('Disk space', { text: body.text, customised: true }) })
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
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))
    fireEvent.change(textarea(), { target: { value: '{nope}' } })

    expect(await within(editor()).findByRole('alert', {}, { timeout: 2000 })).toHaveTextContent('Unknown placeholder: {nope}.')
    expect(within(editor()).getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(within(editor()).getByRole('button', { name: 'Send test' })).toBeDisabled()
  })

  it('sends a test and says when Telegram refused it', async () => {
    let status = 'sent'
    setup({ [`POST ${DISK}/test`]: () => ({ status, error: status === 'failed' ? 'No chat id set for nas' : null }) })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Disk space' }))

    fireEvent.click(within(editor()).getByRole('button', { name: 'Send test' }))
    expect(await within(editor()).findByRole('status')).toHaveTextContent('Test sent to Telegram')

    status = 'failed'
    fireEvent.click(within(editor()).getByRole('button', { name: 'Send test' }))
    expect(await within(editor()).findByText('Not sent: No chat id set for nas.')).toBeInTheDocument()
  })

  it('resets a changed message to the built-in text', async () => {
    const HOLDING = '/api/alerts/templates/Holding line'
    setup({
      [`POST ${HOLDING}/preview`]: { html: 'x', error: null },
      [`DELETE ${HOLDING}`]: tpl('Holding line', { group: 'Reports', parent: 'portfolio_report', category: null }),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Edit Holding line' }))
    const form = screen.getByRole('form', { name: 'Edit Holding line' })
    expect(within(form).getByText(/inside the portfolio report/)).toBeInTheDocument()

    fireEvent.click(within(form).getByRole('button', { name: 'Reset to default' }))
    expect(await within(form).findByRole('status')).toHaveTextContent('Back to the built-in text.')
    expect(within(form).getByRole('textbox', { name: 'Message text' })).toHaveValue('{icon} <b>{pool} is full</b>')
    expect(screen.queryByText('Customised')).not.toBeInTheDocument()
  })

  it('shows save errors from the hub', async () => {
    setup({ [`PUT ${DISK}`]: failWith(422, { detail: '<b> is never closed.' }) })
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
    expect(await screen.findByRole('alert')).toHaveTextContent('The messages are not available right now.')
  })
})

describe('TelegramText', () => {
  it('renders the allowed tags and entities, never raw HTML', () => {
    const { container } = render(<TelegramText html={'❌ <b>Disk &lt;sdb&gt;</b> <i>a &amp; b</i> <code>x</code>'} />)
    expect(container.querySelector('strong')).toHaveTextContent('Disk <sdb>')
    expect(container.querySelector('em')).toHaveTextContent('a & b')
    expect(container.querySelector('code')).toHaveTextContent('x')
    expect(container.querySelector('script')).toBeNull()
  })

  it('keeps the text of an unclosed tag', () => {
    const { container } = render(<TelegramText html="<b>half" />)
    expect(container).toHaveTextContent('half')
  })
})
