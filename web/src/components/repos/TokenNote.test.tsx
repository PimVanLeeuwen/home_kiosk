import { render, screen } from '@testing-library/react'
import { TokenNote } from './TokenNote'

const NOW = new Date('2026-10-09T10:00:00Z')

describe('TokenNote', () => {
  it('says a token has expired, in red', () => {
    render(<TokenNote now={NOW} token={{ owners: ['Hubble'], expires_at: '2026-10-07T10:00:00Z', checked: true }} />)
    const note = screen.getByText(/expired on Wed 7 Oct 2026/)
    expect(note).toHaveClass('text-down')
  })

  it('says when a token has no expiry date', () => {
    render(<TokenNote now={NOW} token={{ owners: ['Mine'], expires_at: null, checked: true }} />)
    expect(screen.getByText('GitHub token: no expiry date.')).toBeInTheDocument()
  })

  it('counts down to the last days', () => {
    render(<TokenNote now={NOW} token={{ owners: ['Mine'], expires_at: '2026-10-11T09:00:00Z', checked: true }} />)
    const note = screen.getByText(/expires Sun 11 Oct 2026 \(in 1 day\)/)
    expect(note).toHaveClass('text-down')
  })
})
