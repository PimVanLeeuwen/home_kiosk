import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { Laundry, Machine } from '../../lib/types'
import { stubApi } from '../../test/stubApi'
import { LaundryCard } from './LaundryCard'
import { useApi } from '../../lib/useApi'

/** The card as Home gives it its data. */
function Fetched() {
  const { data } = useApi<Laundry>('/api/laundry')
  return <LaundryCard data={data} />
}

const at = (h: number, m: number) => new Date(2026, 9, 14, h, m).toISOString()
const base = { online: true, door_open: false, error: null, done_at: null, program: null, remaining_minutes: null, total_minutes: null, ready_at: null }
const washer = (over: Partial<Machine>): Machine => ({ id: 'w', name: 'Washing machine', kind: 'washer', state: 'idle', ...base, ...over })
const dryer = (over: Partial<Machine>): Machine => ({ id: 'd', name: 'Tumble dryer', kind: 'dryer', state: 'idle', ...base, ...over })
const running = { state: 'running' as const, program: 'Cotton', remaining_minutes: 38, total_minutes: 95, ready_at: at(10, 52) }

function show(machines: Machine[], showing = true, stale = false) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 14, 10, 14))
  stubApi({ '/api/laundry': { as_of: at(10, 13), stale, machines, showing } satisfies Laundry })
  render(<MemoryRouter><Fetched /></MemoryRouter>)
}

afterEach(() => vi.useRealTimers())

const machine = async (name: string) => (await screen.findAllByRole('listitem')).find((li) => li.textContent?.includes(name))!

describe('LaundryCard', () => {
  it('shows a running washer with minutes left, its program and ready time, the dryer dimmed', async () => {
    show([washer(running), dryer({})])

    expect(await screen.findByText('Washer running')).toBeInTheDocument()
    const w = await machine('Washing machine')
    expect(w).toHaveAttribute('data-state', 'running')
    expect(within(w).getByText('38')).toBeInTheDocument()
    expect(within(w).getByText('Cotton')).toBeInTheDocument()
    expect(within(w).getByText('Ready at 10:52')).toBeInTheDocument()
    expect(w.querySelector('[data-water]')).toHaveClass('motion-safe:animate-drum')
    expect(await machine('Tumble dryer')).toHaveClass('opacity-45')
    expect(screen.getByText('Updated 1 min ago · ConnectLife')).toBeInTheDocument()
  })

  it('says both are running', async () => {
    show([washer(running), dryer({ ...running, program: 'Towels' })])
    expect(await screen.findByText('Both running')).toBeInTheDocument()
  })

  it('a finished machine says take it out', async () => {
    show([washer({}), dryer({ state: 'done', done_at: at(9, 41) })])

    expect(await screen.findByText('Done')).toBeInTheDocument()
    const d = await machine('Tumble dryer')
    expect(within(d).getByText('Done at 09:41')).toBeInTheDocument()
    expect(within(d).getByText('Take it out')).toHaveClass('text-up')
  })

  it('paused stands still in amber', async () => {
    show([washer({ ...running, state: 'paused', ready_at: null }), dryer({})])

    expect(await screen.findByText('Paused', { selector: 'span.inline-block' })).toBeInTheDocument()
    const w = await machine('Washing machine')
    expect(w.querySelector('[data-water]')).not.toHaveClass('motion-safe:animate-drum')
  })

  it('an error shows the code, or the reason ConnectLife names', async () => {
    show([washer({ state: 'error', error: 'F05' }), dryer({ state: 'error', error: 'Unbalanced load' })])

    expect(await screen.findByText('Needs a look')).toBeInTheDocument()
    expect(within(await machine('Washing machine')).getByText('Error F05')).toHaveClass('text-down')
    expect(within(await machine('Washing machine')).getByText('See the manual')).toBeInTheDocument()
    expect(within(await machine('Tumble dryer')).getAllByText('Unbalanced load').length).toBeGreaterThan(0)
  })

  it('stays hidden when nothing needs attention, and marks stale figures', async () => {
    show([washer({}), dryer({})], false)
    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('region')).toBeNull()
  })

  it('marks stale figures', async () => {
    show([washer(running), dryer({})], true, true)
    expect(await screen.findByText('Showing the last known figures.')).toBeInTheDocument()
  })
})
