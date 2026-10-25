import { render, screen } from '@testing-library/react'
import type { Briefing } from '../../lib/types'
import { BriefingCard } from './BriefingCard'

const BRIEFING: Briefing = {
  as_of: new Date(2026, 9, 29, 6, 30).toISOString(), stale: false, date: '2026-10-29',
  until: new Date(2026, 9, 29, 9, 0).toISOString(),
  line: 'A quiet night. Train on time, dry until 16:00.',
  facts: ['Backup done 03:41', 'Sonarr updated', 'Train on time, platform 4', 'Stand-up 09:30'],
  paragraph: 'Good morning.',
}

describe('BriefingCard', () => {
  it('shows the line and the four facts, marked as written by Claude', () => {
    render(<BriefingCard data={BRIEFING} />)

    expect(screen.getByRole('region', { name: 'Briefing · Thursday' })).toBeInTheDocument()
    expect(screen.getByText('A quiet night. Train on time, dry until 16:00.')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual(BRIEFING.facts)
    expect(screen.getByText('written by Claude')).toBeInTheDocument()
    expect(screen.getByText('As of 06:30')).toBeInTheDocument()
  })
})
