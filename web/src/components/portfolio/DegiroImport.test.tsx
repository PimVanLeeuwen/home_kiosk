import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { DegiroPreview, DegiroRow } from '../../lib/portfolioTypes'
import { PORTFOLIO_FULL } from '../../test/portfolioFixtures'
import { renderRoute } from '../../test/renderRoute'
import { failWith, sentBody, stubApi } from '../../test/stubApi'

const row = (over: Partial<DegiroRow>): DegiroRow => ({
  line: 2,
  date: '2026-10-02T07:05:00Z',
  product: 'ASML HOLDING',
  isin: 'NL0010273215',
  type: 'BUY',
  quantity: 1,
  price: 1597,
  currency: 'EUR',
  fee: 3,
  order_id: 'ord-2',
  status: 'new',
  symbol: 'ASML.AS',
  data_source: 'YAHOO',
  ...over,
})

const ETF = { isin: 'IE00BM67HT60', product: 'XTRACKERS MSCI WORLD IT' }
const FIRST: DegiroPreview = {
  rows: [
    row({ line: 2, status: 'exists', symbol: 'NVDA', type: 'SELL' }),
    row({ line: 3 }),
    row({ line: 4, ...ETF, status: 'unknown', symbol: null, data_source: null }),
  ],
  skipped: ['Line 5: not a trade (no product).'],
  unknown: [
    {
      ...ETF,
      candidates: [
        { symbol: 'XDWT.L', data_source: 'YAHOO', name: 'Xtrackers (London)', currency: 'GBP', held: false },
        { symbol: 'XDWT.DE', data_source: 'YAHOO', name: 'Xtrackers MSCI World IT', currency: 'EUR', held: true },
      ],
    },
  ],
  accounts: [
    { id: 'acc-other', name: 'Savings' },
    { id: 'acc-degiro', name: 'DEGIRO' },
  ],
  account_id: 'acc-degiro',
  counts: { new: 1, exists: 1, unknown: 1 },
}
const CHOSEN: DegiroPreview = {
  ...FIRST,
  rows: [FIRST.rows[0], FIRST.rows[1], row({ line: 4, ...ETF, symbol: 'XDWT.DE', quantity: 2, price: 95.5 })],
  unknown: [],
  counts: { new: 2, exists: 1, unknown: 0 },
}
const CSV = 'Date,Time,Product,ISIN,Quantity,Price\n'

function upload() {
  const input = document.querySelector<HTMLInputElement>('input[type=file]')!
  fireEvent.change(input, { target: { files: [new File([CSV], 'Transactions.csv', { type: 'text/csv' })] } })
}

function setup(over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({
    '/api/portfolio': PORTFOLIO_FULL,
    'POST /api/portfolio/degiro/preview': (body: unknown) =>
      Object.keys((body as { choices: object }).choices).length ? CHOSEN : FIRST,
    'POST /api/portfolio/degiro/import': { imported: 2, existing: 1, unknown: 0 },
    ...over,
  })
  return { fetchMock, ...renderRoute('/portfolio?import') }
}

describe('DegiroImport', () => {
  it('is reached from the Portfolio header', async () => {
    stubApi({ '/api/portfolio': PORTFOLIO_FULL })
    renderRoute('/portfolio')
    expect(await screen.findByRole('link', { name: 'Update from DEGIRO' })).toHaveAttribute('href', '/portfolio?import')
  })

  it('previews the file, asks for unknown products and imports the new trades', async () => {
    const { fetchMock } = setup()

    upload()
    expect(await screen.findByText(/3 trades in the file/)).toHaveTextContent(
      '3 trades in the file: 1 new, 1 already in Ghostfolio, 1 needs a symbol.',
    )
    expect(sentBody(fetchMock, 'POST', '/api/portfolio/degiro/preview')).toEqual({ csv: CSV, choices: {} })
    expect(screen.getByRole('combobox', { name: 'Ghostfolio account' })).toHaveValue('acc-degiro')
    expect(screen.getByText('1 line left out')).toBeInTheDocument()

    // Choosing the held listing previews again; the choice stays on screen.
    const pick = screen.getByRole('combobox', { name: /XTRACKERS MSCI WORLD IT/ })
    fireEvent.change(pick, { target: { value: 'YAHOO/XDWT.DE' } })
    expect(await screen.findByText('2 new')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /XTRACKERS MSCI WORLD IT/ })).toHaveValue('YAHOO/XDWT.DE')

    const table = screen.getByRole('table', { name: 'New trades' })
    expect(within(table).getAllByRole('row')).toHaveLength(3)

    fireEvent.click(screen.getByRole('button', { name: 'Import 2 new trades' }))
    expect(await screen.findByText(/Imported 2 trades into Ghostfolio/)).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', '/api/portfolio/degiro/import')).toEqual({
      csv: CSV,
      account_id: 'acc-degiro',
      choices: { IE00BM67HT60: { data_source: 'YAHOO', symbol: 'XDWT.DE' } },
    })
  })

  it('explains a wrong file', async () => {
    setup({
      'POST /api/portfolio/degiro/preview': failWith(422, {
        detail: 'This does not look like a DEGIRO Transactions export: no column for isin.',
      }),
    })
    upload()
    expect(await screen.findByRole('alert')).toHaveTextContent('does not look like a DEGIRO Transactions export')
  })

  it('has nothing to import when everything is there', async () => {
    const all: DegiroPreview = { ...CHOSEN, rows: [FIRST.rows[0]], counts: { new: 0, exists: 1, unknown: 0 } }
    setup({ 'POST /api/portfolio/degiro/preview': all })
    upload()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Nothing new to import' })).toBeDisabled())
  })
})
