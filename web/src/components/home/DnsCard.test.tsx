import { render, screen } from '@testing-library/react'
import type { DnsStats } from '../../lib/types'
import { DnsCard } from './DnsCard'

const DNS: DnsStats = {
  as_of: new Date(2026, 9, 25, 14, 0).toISOString(), stale: false, answering: true, failing_since: null,
  protection: true, queries: 12480, blocked: 1530, share: 12.3,
  hours: Array.from({ length: 24 }, (_, i) => ({ queries: 500, blocked: 40 + i })),
  top_blocked: 'doubleclick.net', top_blocked_count: 312,
}

function show(data: DnsStats | undefined, error?: Error) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 25, 14, 1))
  render(<DnsCard data={data} error={error} />)
}

afterEach(() => vi.useRealTimers())

describe('DnsCard', () => {
  it('shows the blocked lookups, the share, the hours and the most-blocked domain', () => {
    show(DNS)

    expect(screen.getByText('1.530')).toBeInTheDocument()
    expect(screen.getByText('12.480')).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: '12% of lookups blocked' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Blocked lookups per hour, the last 24 hours' })).toBeInTheDocument()
    expect(screen.getByText('doubleclick.net')).toBeInTheDocument()
    expect(screen.getByText('312×')).toBeInTheDocument()
    expect(screen.getByText('Updated 1 min ago · AdGuard Home')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says when AdGuard is not answering, without a second stale note', () => {
    show({ ...DNS, answering: false, stale: true })

    expect(screen.getByRole('status')).toHaveTextContent('AdGuard is not answering')
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('says when blocking is paused', () => {
    show({ ...DNS, protection: false })

    expect(screen.getByRole('status')).toHaveTextContent('Blocking is paused')
  })

  it('leaves the ring and the domain out before any query', () => {
    show({ ...DNS, queries: 0, blocked: 0, share: null, top_blocked: null, top_blocked_count: null })

    expect(screen.queryByRole('meter')).not.toBeInTheDocument()
    expect(screen.queryByText('Most blocked')).not.toBeInTheDocument()
  })

  it('shows loading until the first answer', () => {
    show(undefined)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('says AdGuard Home is unavailable on an error', () => {
    show(undefined, new Error('503'))
    expect(screen.getByText('AdGuard Home is not available right now.')).toBeInTheDocument()
  })
})
