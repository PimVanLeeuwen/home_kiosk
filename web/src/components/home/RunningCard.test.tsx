import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { runningState } from '../../lib/homeStates'
import { localDate } from '../../lib/running'
import { overview, SESSION } from '../../test/runningFixtures'
import { RunningCard } from './RunningCard'

const today = { ...SESSION, date: localDate(new Date()) }

describe('RunningCard', () => {
  it("shows today's session until it is run, then the run", () => {
    const before = overview({ today: { ran: false, session: today } })
    const { rerender } = render(<RunningCard data={before} />, { wrapper: MemoryRouter })
    expect(screen.getByRole('region', { name: 'Today: Threshold Intervals' })).toHaveTextContent('8,3 km · 45m - 50m')

    rerender(<RunningCard data={overview({ today: { ran: true, session: today } })} />)
    const ran = screen.getByRole('region', { name: 'Ran today' })
    expect(ran).toHaveTextContent('10,4')
    expect(ran).toHaveTextContent('5:12 /km · 54:08')
    expect(ran).toHaveTextContent('Runna: Threshold Intervals')
  })

  it('is live on a session day, calm once run, gone on a rest day', () => {
    expect(runningState(overview({ today: { ran: false, session: today } }))).toBe('live')
    expect(runningState(overview({ today: { ran: true, session: today } }))).toBe('quiet')
    expect(runningState(overview())).toBe('hidden')
    expect(runningState(undefined)).toBe('hidden')
  })
})
