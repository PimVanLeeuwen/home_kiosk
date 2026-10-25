import { fireEvent, render, screen } from '@testing-library/react'
import type { AiStatus } from '../../lib/types'
import { failWith, stubApi } from '../../test/stubApi'
import { AiSettings } from './AiSettings'

const AI: AiStatus = {
  as_of: '', stale: false, configured: true, cap: 5, spent: 0.42, calls: 31, capped: false,
  features: [{ id: 'update_notes', label: 'Update notes', on: false }],
}

describe('AiSettings', () => {
  it('shows this month’s spend against the cap', async () => {
    stubApi({ '/api/ai': AI })
    render(<AiSettings />)

    expect(await screen.findByText('0.42 of 5.00 · 31 calls')).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Spent this month' })).toHaveAttribute('aria-valuenow', '8')
  })

  it('switches a feature on through the hub', async () => {
    const fetchMock = stubApi({
      '/api/ai': AI,
      'PUT /api/ai/features': { ...AI, features: [{ ...AI.features[0], on: true }] },
    })
    render(<AiSettings />)

    fireEvent.click(await screen.findByRole('switch', { name: 'Update notes' }))

    expect(await screen.findByRole('switch', { name: 'Update notes' })).toHaveAttribute('aria-checked', 'true')
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')!
    expect(JSON.parse(String(put[1]!.body))).toEqual({ update_notes: true })
  })

  it('says the reason when a switch does not save', async () => {
    stubApi({ '/api/ai': AI, 'PUT /api/ai/features': failWith(422, { detail: 'unknown feature: x' }) })
    render(<AiSettings />)

    fireEvent.click(await screen.findByRole('switch', { name: 'Update notes' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('unknown feature: x')
  })

  it('says when the cap is reached, and when there is no key', async () => {
    stubApi({ '/api/ai': { ...AI, spent: 5.01, capped: true } })
    const { unmount } = render(<AiSettings />)
    expect(await screen.findByText(/The cap is reached/)).toBeInTheDocument()
    unmount()

    stubApi({ '/api/ai': { ...AI, configured: false, features: [] } })
    render(<AiSettings />)
    expect(await screen.findByText(/No API key/)).toBeInTheDocument()
    expect(screen.getByText(/update notes first/)).toBeInTheDocument()
  })

  it('says AI is unavailable when the hub does not answer', async () => {
    stubApi({})
    render(<AiSettings />)

    expect(await screen.findByText(/AI is not available right now/)).toBeInTheDocument()
  })

  it('writes the morning digest now and says what was sent', async () => {
    const withDigest = { ...AI, features: [{ id: 'briefing', label: 'Morning digest', on: true }] }
    stubApi({ '/api/ai': withDigest, 'POST /api/ai/briefing/now': { line: 'A quiet night.' } })
    render(<AiSettings />)

    fireEvent.click(await screen.findByRole('button', { name: 'Write one now' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Sent to Telegram: A quiet night.')
  })

  it('says why no digest was written', async () => {
    const withDigest = { ...AI, features: [{ id: 'briefing', label: 'Morning digest', on: true }] }
    stubApi({ '/api/ai': withDigest, 'POST /api/ai/briefing/now': failWith(409, { detail: 'The cap is reached.' }) })
    render(<AiSettings />)

    fireEvent.click(await screen.findByRole('button', { name: 'Write one now' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The cap is reached.')
  })
})
