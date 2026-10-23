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
const tile = (scope: ReturnType<typeof within>, label: string) => scope.getByRole('region', { name: label })

describe('PortfolioPage', () => {
  it('sums up value, today, total gain, invested and cash', async () => {
    setup()

    await screen.findByRole('region', { name: 'Summary' })
    // The value itself leads the Value card; today's move is the header's pill (once, not in the card too).
    const value = screen.getByRole('region', { name: 'Value' })
    expect(within(value).getByText('€ 9.143')).toBeInTheDocument()
    expect(within(value).queryByText(/today$/)).not.toBeInTheDocument()
    expect(screen.getByText(/today$/, { selector: '.uppercase' })).toHaveTextContent(/^−0,0\d% today$/)
    // Today is the sum of the holdings' moves, like the daily report: 22,11 + 7,88 - 32.
    expect(tile(summary(), 'Today')).toHaveTextContent('−€ 2')
    expect(tile(summary(), 'Total gain')).toHaveTextContent('+€ 4.452+103,87%')
    expect(tile(summary(), 'Invested')).toHaveTextContent('€ 6.069')
    expect(tile(summary(), 'Cash')).toHaveTextContent('€ 12€ 85 dividends')
  })

  it('charts the value with the gain apart from deposits, per period', async () => {
    const { fetchMock } = setup('/portfolio', {
      '/api/portfolio/history?range=max': { ...HISTORY, range: 'max' },
    })

    const card = await screen.findByRole('region', { name: 'Value' })
    // (9155 - 6069) - (6000 - 5000) = 2086
    expect(await within(card).findByText('+€ 2.086')).toBeInTheDocument()
    expect(within(card).getByRole('img', { name: /Portfolio value, 1Y: from €\s6\.000 to €\s9\.155\./ })).toBeInTheDocument()

    // The chart is green for a rising period, glows, and marks the period's high.
    const chart = within(card).getByRole('img', { name: /Portfolio value, 1Y/ }).parentElement!
    expect(chart).toHaveAttribute('data-tone', 'up')
    expect(within(card).getByText(/^high €\s9\.155$/)).toBeInTheDocument()
    expect(within(card).getByRole('radio', { name: '1Y' })).toHaveAttribute('aria-checked', 'true')

    fireEvent.click(within(card).getByRole('radio', { name: 'Max' }))
    expect(await within(card).findByText(/Gain since the start/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/portfolio/history?range=max', expect.anything())
  })

  it('draws a falling period in red', async () => {
    const points = [...HISTORY.points].reverse().map((p, i) => ({ ...p, d: HISTORY.points[i].d }))
    setup('/portfolio', { '/api/portfolio/history?range=year': { ...HISTORY, points } })

    const card = await screen.findByRole('region', { name: 'Value' })
    const chart = (await within(card).findByRole('img', { name: /Portfolio value, 1Y/ })).parentElement!
    expect(chart).toHaveAttribute('data-tone', 'down')
  })

  it('lists holdings sortable by value, today and gain', async () => {
    setup()

    const card = await screen.findByRole('region', { name: 'Holdings (3)' })
    const table = within(card).getByRole('table')
    const symbols = () => within(table).getAllByRole('link').map((l) => l.firstElementChild?.textContent)
    expect(symbols()).toEqual(['ASML.AS', 'NVDA', 'XDWT.DE'])
    fireEvent.click(within(card).getByRole('radio', { name: 'Today' }))
    expect(symbols()).toEqual(['NVDA', 'XDWT.DE', 'ASML.AS'])
    fireEvent.click(within(card).getByRole('radio', { name: 'Gain' }))
    expect(symbols()).toEqual(['NVDA', 'ASML.AS', 'XDWT.DE'])

    expect(within(table).getAllByRole('link')[0]).toHaveAttribute('href', '/portfolio?h=YAHOO%2FNVDA')
    // Today as a tinted pill, and a thin bar for the weight against the biggest holding.
    const first = within(table).getAllByRole('row')[1]
    expect(within(first).getByText('+1,09%')).toHaveClass('text-up')
    expect((first.querySelector('[aria-hidden="true"] > span') as HTMLElement).style.width).toMatch(/^97\.39/)
    // The movers sit above, one tile per holding.
    const movers = screen.getByRole('region', { name: "Today's movers" })
    expect(movers).toHaveTextContent('2 up · 1 down')
  })

  it('shows allocation and markets', async () => {
    setup()

    const allocation = await screen.findByRole('region', { name: 'Allocation' })
    // The legend, with the largest slice also named in the ring's middle.
    expect(within(allocation).getByText('Equities', { selector: 'span' }).nextElementSibling).toHaveTextContent('65,3%')
    const ring = within(allocation).getByRole('img', { name: 'Allocation: Equities 65,3%, ETFs 34,6%, Cash 0,1%' })
    expect(ring).toHaveTextContent('65%Equities')
    expect(ring.querySelectorAll('circle')).toHaveLength(4) // the track and a slice each
    const markets = await screen.findByRole('region', { name: 'Markets' })
    expect(within(markets).getByText('AEX').parentElement).toHaveTextContent('AEX1.102,63−1,10%')
    expect(within(markets).getByText('−1,10%')).toHaveClass('text-down')
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
    // A coloured chip per type, a gain pill in the header, and the chart edge to edge.
    expect(within(rows[0]).getByText('Sell')).toHaveStyle({ color: '#7cc4ff' })
    expect(screen.getByText('+120,62% gain')).toHaveClass('text-up')
    expect(screen.getByRole('img', { name: /NVDA price since you first bought it/ }).parentElement).toHaveClass('-mx-5')
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Portfolio' })).toHaveAttribute('href', '/portfolio')
  })

  it('says when Ghostfolio is down', async () => {
    setup('/portfolio', { '/api/portfolio': new Error('down') })
    expect(await screen.findByText(/The portfolio is not available right now/)).toBeInTheDocument()
  })
})
