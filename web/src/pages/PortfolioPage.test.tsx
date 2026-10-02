import { fireEvent, screen, within } from '@testing-library/react'
import { HISTORY, INDICES, NVDA, PORTFOLIO_FULL } from '../test/portfolioFixtures'
import { renderRoute } from '../test/renderRoute'
import { stubApi } from '../test/stubApi'

function setup(path = '/portfolio', over: Record<string, unknown> = {}) {
  const fetchMock = stubApi({
    '/api/portfolio': PORTFOLIO_FULL,
    '/api/portfolio/history?range=year': HISTORY,
    '/api/indices': INDICES,
    '/api/portfolio/holdings/YAHOO/NVDA': NVDA,
    ...over,
  })
  return { fetchMock, ...renderRoute(path) }
}

const summary = () => within(screen.getByRole('region', { name: 'Summary' }))
const figure = (scope: ReturnType<typeof within>, label: string) => scope.getByText(label).nextElementSibling

describe('PortfolioPage', () => {
  it('sums up value, today, total gain, invested and cash', async () => {
    setup()

    await screen.findByRole('region', { name: 'Summary' })
    expect(summary().getByText('€ 9.143')).toBeInTheDocument()
    // Today is the sum of the holdings' moves, like the daily report: 22,11 + 7,88 - 32.
    expect(figure(summary(), 'Today')).toHaveTextContent('−€ 2')
    expect(figure(summary(), 'Total gain')).toHaveTextContent('+€ 4.452+103,87%')
    expect(figure(summary(), 'Invested')).toHaveTextContent('€ 6.069')
    expect(figure(summary(), 'Cash')).toHaveTextContent('€ 12€ 85 dividends')
  })

  it('charts the value with the gain apart from deposits, per period', async () => {
    const { fetchMock } = setup('/portfolio', {
      '/api/portfolio/history?range=max': { ...HISTORY, range: 'max' },
    })

    const card = await screen.findByRole('region', { name: 'Value' })
    // (9155 - 6069) - (6000 - 5000) = 2086
    expect(await within(card).findByText('+€ 2.086')).toBeInTheDocument()
    expect(within(card).getByRole('img', { name: /Portfolio value, 1Y: from €\s6\.000 to €\s9\.155\./ })).toBeInTheDocument()

    fireEvent.click(within(card).getByRole('button', { name: 'Max' }))
    expect(await within(card).findByText(/Gain since the start/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/portfolio/history?range=max', expect.anything())
  })

  it('lists holdings sortable by value, today and gain', async () => {
    setup()

    const card = await screen.findByRole('region', { name: 'Holdings (3)' })
    const table = within(card).getByRole('table')
    const symbols = () => within(table).getAllByRole('link').map((l) => l.firstElementChild?.textContent)
    expect(symbols()).toEqual(['ASML.AS', 'NVDA', 'XDWT.DE'])
    fireEvent.click(within(card).getByRole('button', { name: 'Today' }))
    expect(symbols()).toEqual(['NVDA', 'XDWT.DE', 'ASML.AS'])
    fireEvent.click(within(card).getByRole('button', { name: 'Gain' }))
    expect(symbols()).toEqual(['NVDA', 'ASML.AS', 'XDWT.DE'])

    expect(within(table).getAllByRole('link')[0]).toHaveAttribute('href', '/portfolio?h=YAHOO%2FNVDA')
  })

  it('shows allocation and markets', async () => {
    setup()

    const allocation = await screen.findByRole('region', { name: 'Allocation' })
    expect(within(allocation).getByText('Equities').nextElementSibling).toHaveTextContent('65,3%')
    const markets = await screen.findByRole('region', { name: 'Markets' })
    expect(within(markets).getByText('AEX').parentElement).toHaveTextContent('AEX1.102,63−1,10%')
  })

  it('opens a holding with its figures, price chart and transactions', async () => {
    setup('/portfolio?h=YAHOO%2FNVDA')

    expect(await screen.findByRole('heading', { name: 'NVDA', level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/NVIDIA Corporation · held since 6 Nov 2023/)).toBeInTheDocument()
    const position = screen.getByRole('region', { name: 'Position' })
    expect(figure(within(position), 'Average price')).toHaveTextContent('US$ 169,85')
    expect(figure(within(position), 'Gain')).toHaveTextContent('+€ 1.837 · +120,62%')
    expect(screen.getByRole('img', { name: /NVDA price since you first bought it/ })).toBeInTheDocument()

    const rows = within(screen.getByRole('region', { name: 'Transactions' })).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('9 Sept 2024Sell5')
    // No euro value from Ghostfolio: the amount in the trade's own currency.
    expect(rows[1]).toHaveTextContent('US$ 454,91')
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Portfolio' })).toHaveAttribute('href', '/portfolio')
  })

  it('says when Ghostfolio is down', async () => {
    setup('/portfolio', { '/api/portfolio': new Error('down') })
    expect(await screen.findByText(/The portfolio is not available right now/)).toBeInTheDocument()
  })
})
