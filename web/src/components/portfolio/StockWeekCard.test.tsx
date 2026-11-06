import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { PORTFOLIO_FULL, WEEKS } from '../../test/portfolioFixtures'
import { failWith, stubApi } from '../../test/stubApi'
import { StockWeekCard } from './StockWeekCard'

function setup(weeks: unknown = WEEKS, random = () => 0) {
  stubApi({ '/api/portfolio/weeks': weeks })
  render(
    <MemoryRouter>
      <StockWeekCard holdings={PORTFOLIO_FULL.holdings} random={random} />
    </MemoryRouter>,
  )
}

const card = () => screen.getByRole('region', { name: 'This week' })

describe('StockWeekCard', () => {
  it('shows a holding with its week, price, today and your gain', async () => {
    setup()
    const link = await screen.findByRole('link', { name: 'NVDA' })
    expect(link).toHaveAttribute('href', '/portfolio?h=YAHOO%2FNVDA')
    const c = within(card())
    expect(c.getByText('NVIDIA Corporation')).toBeInTheDocument()
    expect(c.getByText('+10,00%')).toHaveClass('text-up')
    expect(c.getByText('+1,09% today')).toBeInTheDocument()
    expect(c.getByText('Yours +120,62%')).toBeInTheDocument()
    // The chart: green, its days, its high and low, and the previous close it is measured from.
    const chart = c.getByRole('img', { name: 'NVDA over its last five trading days' }).parentElement!
    expect(chart).toHaveAttribute('data-tone', 'up')
    expect(card()).toHaveTextContent(/Previous close US\$\s100,00/)
    expect(c.getByText('Fri')).toBeInTheDocument()
    expect(c.getByText('Mon')).toBeInTheDocument()
    expect(c.getByText(/^US\$\s99,00$/)).toBeInTheDocument()
  })

  it('shuffles to another holding, never one that was sold', async () => {
    setup()
    await screen.findByRole('link', { name: 'NVDA' })
    fireEvent.click(within(card()).getByRole('button', { name: 'Show another holding' }))
    expect(await screen.findByRole('link', { name: 'ASML.AS' })).toBeInTheDocument()
    expect(within(card()).getByText('−7,50%')).toHaveClass('text-down')
    fireEvent.click(within(card()).getByRole('button', { name: 'Show another holding' }))
    expect(await screen.findByRole('link', { name: 'NVDA' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'GONE' })).not.toBeInTheDocument()
  })

  it('starts on a random holding', async () => {
    setup(WEEKS, () => 0.9)
    expect(await screen.findByRole('link', { name: 'ASML.AS' })).toBeInTheDocument()
  })

  it('says when the weeks are stale, missing or unavailable', async () => {
    setup({ ...WEEKS, stale: true })
    expect(await within(card()).findByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('says when there is no week yet', async () => {
    setup({ ...WEEKS, stocks: [] })
    expect(await screen.findByText('No week of prices for your holdings yet.')).toBeInTheDocument()
  })

  it('says when the weeks cannot be had', async () => {
    setup(failWith(503, {}))
    expect(await screen.findByText(/The week's prices are not available right now/)).toBeInTheDocument()
  })

  it('shows loading first', () => {
    setup()
    expect(within(card()).getByRole('status')).toHaveTextContent('Loading the week…')
  })
})
