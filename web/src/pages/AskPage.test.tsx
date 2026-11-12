import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { AskAnswer } from '../lib/ask'
import type { AiStatus } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const AI: AiStatus = {
  as_of: '2026-11-12T15:00:00Z', stale: false, configured: true, cap: 10, spent: 0.42, calls: 30, capped: false,
  features: [{ id: 'ask', label: 'Ask', on: true }],
}
const DIM = { id: 't1', tool: 'lights_change', args: { group: 'spots', brightness: 40 }, title: 'Dim the Spots to 40%', detail: 'now at 80%' }
const ANSWER: AskAnswer = { text: 'The **07:16** is on time.', used: ['train'], proposals: [], spent: 0.43, cap: 10 }

function ask(text: string) {
  const box = screen.getByLabelText('Your question')
  fireEvent.change(box, { target: { value: text } })
  fireEvent.keyDown(box, { key: 'Enter' })
}

describe('AskPage', () => {
  it('answers a question with the tools it used and the month’s spend', async () => {
    const fetchMock = stubApi({ '/api/ai': AI, 'POST /api/ask': ANSWER })
    renderRoute('/ask')

    expect(await screen.findByText('Ask the house')).toBeInTheDocument()
    ask('  Is my train on time?  ')

    const thread = await screen.findByRole('list', { name: 'Conversation' })
    expect(await within(thread).findByText('07:16')).toHaveProperty('tagName', 'STRONG')
    expect(thread).toHaveTextContent('Is my train on time?')
    expect(thread).toHaveTextContent('Usedtrain')
    expect(sentBody(fetchMock, 'POST', '/api/ask')).toEqual({ messages: [{ role: 'user', text: 'Is my train on time?' }] })
    expect(screen.getAllByText(/€0.43/).length).toBeGreaterThan(0)
  })

  it('makes a change only after Confirm, and a follow-up carries the outcome', async () => {
    const fetchMock = stubApi({
      '/api/ai': AI,
      'POST /api/ask': { ...ANSWER, text: 'I proposed dimming the Spots.', used: ['lights'], proposals: [DIM] },
      'POST /api/ask/confirm': { ok: true },
    })
    renderRoute('/ask')
    fireEvent.click(await screen.findByRole('button', { name: 'Turn off the living room lights' }))

    const card = await screen.findByRole('group', { name: 'Dim the Spots to 40%' })
    expect(card).toHaveTextContent('now at 80%')
    expect(fetchMock.mock.calls.some(([p]) => p === '/api/ask/confirm')).toBe(false)
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }))

    expect(await within(card).findByText('Done')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'POST', '/api/ask/confirm')).toEqual({ tool: 'lights_change', args: { group: 'spots', brightness: 40 } })
    ask('Thanks')
    await waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/ask', 1)).toBeDefined())
    expect(sentBody(fetchMock, 'POST', '/api/ask', 1).messages[1].text).toContain('The owner confirmed: Dim the Spots to 40%')
  })

  it('says why a change or a question failed, and starts over with New chat', async () => {
    stubApi({
      '/api/ai': AI,
      'POST /api/ask': { ...ANSWER, proposals: [DIM] },
      'POST /api/ask/confirm': failWith(422, { detail: 'The Hue Bridge did not answer.' }),
    })
    renderRoute('/ask')
    await screen.findByText('Ask the house')
    ask('Dim the spots')

    const card = await screen.findByRole('group', { name: 'Dim the Spots to 40%' })
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }))
    expect(await within(card).findByRole('alert')).toHaveTextContent('The Hue Bridge did not answer.')
    expect(within(card).getByRole('button', { name: 'Try again' })).toBeEnabled()
    fireEvent.click(within(card).getByRole('button', { name: 'Cancel' }))
    expect(within(card).getByText('Cancelled')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    expect(screen.getByText('Ask the house')).toBeInTheDocument()
  })

  it('shows the hub’s reason when the question is refused', async () => {
    stubApi({ '/api/ai': AI, 'POST /api/ask': failWith(429, { detail: 'The AI cap is reached for this month.' }) })
    renderRoute('/ask')
    await screen.findByText('Ask the house')
    ask('What is on tomorrow?')

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI cap is reached for this month.')
  })

  it('points to Settings while Ask is switched off', async () => {
    stubApi({ '/api/ai': { ...AI, features: [{ id: 'ask', label: 'Ask', on: false }] } })
    renderRoute('/ask')

    expect(await screen.findByText('Ask is not switched on')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings, AI' })).toHaveAttribute('href', '/settings/ai')
    expect(screen.getByLabelText('Your question')).toBeDisabled()
  })

  it('sends with Enter but not with Shift+Enter', async () => {
    const fetchMock = stubApi({ '/api/ai': AI, 'POST /api/ask': ANSWER })
    renderRoute('/ask')
    await screen.findByText('Ask the house')
    const box = screen.getByLabelText('Your question')
    fireEvent.change(box, { target: { value: 'Hello' } })
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true })

    expect(fetchMock.mock.calls.some(([p]) => p === '/api/ask')).toBe(false)
  })
})
