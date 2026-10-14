import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { Train, TrainRun } from '../../lib/types'
import { stubApi } from '../../test/stubApi'
import { TrainCard } from './TrainCard'

const at = (h: number, m: number) => new Date(2026, 9, 14, h, m).toISOString()

function run(over: Partial<TrainRun> = {}): TrainRun {
  const shift = (h: number, m: number) => at(h, m + (over.delay_minutes ?? 0))
  return {
    name: 'IC 3522', status: 'on_time', planned_departure: at(7, 16), actual_departure: shift(7, 16),
    delay_minutes: 0, planned_track: '6', actual_track: '6',
    stops: [
      { name: 'Leiden Centraal', planned: at(7, 16), actual: shift(7, 16), track: '6', cancelled: false },
      { name: "Den Haag HS", planned: at(7, 39), actual: shift(7, 39), track: '3', cancelled: false },
      { name: 'Delft', planned: at(8, 11), actual: shift(8, 11), track: '7', cancelled: false },
      { name: 'Rotterdam Centraal', planned: at(8, 28), actual: shift(8, 28), track: '2', cancelled: false },
    ],
    ...over,
  }
}

function payload(over: Partial<Train> = {}): Train {
  return {
    as_of: at(6, 40), stale: false, date: '2026-10-14', route: 'Leiden Centraal to Rotterdam Centraal',
    departure: '07:16', mode: 'morning', watching: true, departed: false, train: run(), next_direct: null,
    disruptions: [], ...over,
  }
}

function show(train: Train | null, now = new Date(2026, 9, 14, 6, 42)) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(now)
  stubApi(train ? { '/api/train': train } : {})
  render(<MemoryRouter><TrainCard /></MemoryRouter>)
}

afterEach(() => vi.useRealTimers())

const card = () => screen.findByRole('region', { name: /train/ })

describe('TrainCard', () => {
  it('shows an on-time train with the minutes to go, its platform and stops', async () => {
    show(payload())

    const c = await card()
    expect(c).toHaveAccessibleName('Your train · direct · Leiden Centraal to Rotterdam Centraal')
    expect(within(c).getByText('On time')).toHaveAttribute('data-tone', 'up')
    expect(within(c).getByText(/Leaves in 34 min from/)).toBeInTheDocument()
    expect(within(c).getByRole('img', { name: '34 min to go' })).toBeInTheDocument()
    expect(within(within(c).getByRole('list', { name: 'Stops' })).getAllByRole('listitem')).toHaveLength(4)
  })

  it('strikes the planned time of a late train and shows the new one at every stop', async () => {
    show(payload({ train: run({ status: 'late', delay_minutes: 6 }) }))

    const c = await card()
    expect(within(c).getByText('6 min late')).toHaveAttribute('data-tone', 'warn')
    // In the departure box and at the first stop.
    expect(within(c).getAllByText('07:22')).toHaveLength(2)
    expect(within(c).getByText('08:34')).toHaveClass('text-warn')
  })

  it('marks a platform change', async () => {
    show(payload({ train: run({ actual_track: '4' }) }))

    const c = await card()
    expect(within(c).getByText('4')).toHaveAttribute('data-changed', 'true')
    expect(within(c).getByText('6').tagName).toBe('S')
  })

  it('gives a cancelled train the next direct one and counts down to that', async () => {
    const next = run({ name: 'IC 3524', planned_departure: at(7, 46), actual_departure: at(7, 46) })
    next.stops = next.stops.map((s) => ({ ...s, planned: at(8, 58), actual: at(8, 58) }))
    show(payload({ train: run({ status: 'cancelled' }), next_direct: next }))

    const c = await card()
    expect(within(c).getByText('Cancelled')).toHaveAttribute('data-tone', 'down')
    expect(within(c).getByText('The 07:16 to Rotterdam Centraal does not run')).toBeInTheDocument()
    expect(within(c).getByText('Next direct train')).toBeInTheDocument()
    expect(within(c).getByText('07:46')).toBeInTheDocument()
    expect(within(c).getByRole('img', { name: '64 min to next' })).toBeInTheDocument()
  })

  it("shows NS's own text for works on the route", async () => {
    show(payload({ disruptions: [{ id: 'w1', kind: 'MAINTENANCE', title: 'Utrecht - Amsterdam.', text: 'Minder treinen.', until: 'Tot 10:00 uur.' }] }))

    const note = within(await card()).getByRole('note')
    expect(note).toHaveTextContent('Utrecht - Amsterdam. Minder treinen. Tot 10:00 uur. (NS)')
  })

  it("the evening before, shows tomorrow's problem without a countdown", async () => {
    show(payload({ mode: 'evening', train: run({ status: 'cancelled' }) }), new Date(2026, 9, 13, 20, 5))

    const c = await card()
    expect(c).toHaveAccessibleName(/^Tomorrow's train/)
    expect(within(c).getByText('The 07:16 to Rotterdam Centraal does not run tomorrow')).toBeInTheDocument()
    expect(within(c).queryByRole('img')).toBeNull()
  })

  it('says when the figures are the last known ones', async () => {
    show(payload({ stale: true }))

    expect(within(await card()).getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('stays hidden when there is nothing to follow, yesterday\'s train, or no answer', async () => {
    show(payload({ watching: false }))
    show(payload({ date: '2026-10-13' }))
    show(null)

    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('region')).toBeNull()
  })
})
