import { fireEvent, render, screen, within } from '@testing-library/react'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { TodoSettings } from './TodoSettings'

const field = () => screen.findByLabelText('Send the daily message at')

describe('TodoSettings', () => {
  it('shows the time of the daily message and saves a new one', async () => {
    const fetchMock = stubApi({ '/api/settings/todos': { at: '08:00' }, 'PUT /api/settings/todos': { at: '07:15' } })
    render(<TodoSettings />)

    const input = await field()
    expect(input).toHaveValue('08:00')
    fireEvent.blur(input) // unchanged: nothing sent
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0)

    fireEvent.change(input, { target: { value: '07:15' } })
    fireEvent.blur(input)
    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', '/api/settings/todos')).toEqual({ at: '07:15' }))
    expect(await field()).toHaveValue('07:15')
  })

  it('says why a change did not save', async () => {
    stubApi({ '/api/settings/todos': { at: '08:00' }, 'PUT /api/settings/todos': failWith(422, { detail: 'Bad time.' }) })
    render(<TodoSettings />)

    const input = await field()
    fireEvent.change(input, { target: { value: '09:30' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(within(await screen.findByRole('alert')).getByText(/Bad time/)).toBeInTheDocument()
  })
})
