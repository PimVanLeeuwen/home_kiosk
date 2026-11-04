import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { remindersState } from '../../lib/homeStates'
import type { Reminders } from '../../lib/reminders'
import { RemindersCard } from './RemindersCard'

const data = (due: Reminders['due'], stale = false): Reminders => ({
  as_of: new Date(2026, 10, 4, 9).toISOString(), stale, today: '2026-11-04', due, reminders: [],
})

describe('RemindersCard', () => {
  it("lists today's reminders and links to the page", () => {
    render(<MemoryRouter><RemindersCard data={data([{ id: 1, title: 'Bins out', at: '07:30', done: false }, { id: 2, title: 'Plants', at: null, done: true }], true)} /></MemoryRouter>)

    expect(screen.getByRole('region', { name: 'Reminders' })).toHaveTextContent('Bins out07:30PlantsAll day')
    expect(screen.getByText('Plants')).toHaveClass('line-through')
    expect(screen.getByRole('link', { name: /All reminders/ })).toHaveAttribute('href', '/reminders')
    expect(screen.getByRole('status')).toHaveTextContent('last known')
  })

  it('shows on Home only on a day with some, live while one is open', () => {
    expect(remindersState(undefined)).toBe('hidden')
    expect(remindersState(data([]))).toBe('hidden')
    expect(remindersState(data([{ id: 1, title: 'x', at: null, done: true }]))).toBe('quiet')
    expect(remindersState(data([{ id: 1, title: 'x', at: null, done: false }]))).toBe('live')
  })
})
