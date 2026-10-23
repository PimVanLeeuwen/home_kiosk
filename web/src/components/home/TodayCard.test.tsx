import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { CalendarEvent, Today } from '../../lib/types'
import { stubApi } from '../../test/stubApi'
import { TodayCard } from './TodayCard'
import { useApi } from '../../lib/useApi'

/** The card as Home gives it its data. */
function Fetched() {
  const { data } = useApi<Today>('/api/calendar')
  return <TodayCard data={data} />
}

const at = (h: number, m = 0) => new Date(2026, 9, 14, h, m).toISOString()
const ev = (s: [number, number], e: [number, number], title: string, calendar: string, color: string): CalendarEvent => ({
  calendar_id: calendar, calendar, color, title, start: at(...s), end: at(...e), all_day: false,
})
const EVENTS = [
  ev([8, 0], [9, 0], 'Gym', 'Personal', '#ffb86b'),
  ev([9, 30], [10, 0], 'Standup', 'Work', '#5aa9ff'),
  ev([12, 30], [13, 30], 'Lunch with Sanne', 'Family', '#c8a0ff'),
]
const TODAY: Today = { as_of: at(9), stale: false, date: '2026-10-14', events: EVENTS, all_day: [], errors: {} }

function show(today: Today | null, h: number, m = 0) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 14, h, m))
  stubApi(today ? { '/api/calendar': today } : {})
  render(<MemoryRouter><Fetched /></MemoryRouter>)
}

afterEach(() => vi.useRealTimers())

describe('TodayCard', () => {
  it('leads with the next event, its calendar and a countdown', async () => {
    show(TODAY, 9, 6)

    const card = await screen.findByRole('region', { name: /^Today · Wed 14 Oct/ })
    expect(within(card).getByText('Next · Work')).toBeInTheDocument()
    expect(within(card).getByText('Standup')).toBeInTheDocument()
    expect(within(card).getByText('09:30 to 10:00')).toBeInTheDocument()
    expect(within(card).getByRole('img', { name: '24 min' })).toBeInTheDocument()
  })

  it('during an event says until when, and strikes past ones in the list', async () => {
    show(TODAY, 12, 54)

    const card = await screen.findByRole('region', { name: /^Today/ })
    expect(within(card).getByText('Now · Family')).toBeInTheDocument()
    expect(within(card).getByText('until 13:30')).toBeInTheDocument()
    const rest = within(within(card).getByRole('list', { name: 'The rest of the day' })).getAllByRole('listitem')
    expect(rest.map((li) => li.dataset.past)).toEqual(['true', 'true'])
  })

  it('draws the day as a ribbon with past blocks dimmed', async () => {
    show(TODAY, 9, 6)

    const ribbon = await screen.findByRole('img', { name: 'The day from 07:00 to 23:00' })
    const blocks = ribbon.querySelectorAll('i')
    expect(blocks).toHaveLength(3)
    expect(blocks[0]).toHaveAttribute('data-past', 'true')
    expect(blocks[1]).not.toHaveAttribute('data-past')
  })

  it('shows all-day events as chips', async () => {
    show({ ...TODAY, all_day: [{ ...EVENTS[0], title: "Mama's birthday", start: null, end: null, all_day: true }] }, 9)

    expect(within(await screen.findByRole('list', { name: 'All day' })).getByText("Mama's birthday")).toBeInTheDocument()
  })

  it('says when nothing more is planned', async () => {
    show(TODAY, 22, 0)

    expect(await screen.findByText('Nothing more today')).toBeInTheDocument()
  })

  it('notes a calendar that could not be read, and stale figures', async () => {
    show({ ...TODAY, stale: true, errors: { 'Bartender Shifts': 'HTTP 503' } }, 9)

    expect(await screen.findByText('Not read just now: Bartender Shifts.')).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it("stays hidden on an empty day, yesterday's answer, or no answer", async () => {
    show({ ...TODAY, events: [] }, 9)
    show({ ...TODAY, date: '2026-10-13' }, 9)
    show(null, 9)

    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByRole('region')).toBeNull()
  })
})
