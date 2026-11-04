import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import type { Reminders } from '../lib/reminders'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const NOW = new Date(2026, 10, 4, 9, 0)
const BINS = {
  id: 1, title: 'Bins out', start: '2026-11-04', at: '07:30', notify: 'evening' as const, next: '2026-11-04',
  repeat: { kind: 'every' as const, every: 2, unit: 'weeks' as const, weekdays: [], day: 1 as const },
}
const DATA: Reminders = {
  as_of: NOW.toISOString(), stale: false, today: '2026-11-04',
  due: [{ id: 1, title: 'Bins out', at: '07:30', done: false }],
  reminders: [BINS],
}

describe('RemindersPage', () => {
  it("shows today's reminders and every reminder with how it repeats", async () => {
    stubApi({ '/api/reminders': DATA })
    renderRoute('/reminders')

    expect(await screen.findByText('1 today')).toBeInTheDocument()
    const today = screen.getByRole('region', { name: 'Today' })
    expect(within(today).getByRole('checkbox', { name: 'Bins out done' })).toHaveAttribute('aria-checked', 'false')
    const all = screen.getByRole('region', { name: 'All reminders' })
    expect(all).toHaveTextContent('Today07:30Bins outEvery 2 weeks · Message the evening before')
  })

  it('adds a weekly reminder and ticks one off', async () => {
    const fetchMock = stubApi({
      '/api/reminders': DATA,
      'POST /api/reminders': DATA,
      'POST /api/reminders/1/done': { ...DATA, due: [{ ...DATA.due[0], done: true }] },
    })
    renderRoute('/reminders')
    const form = await screen.findByRole('form', { name: 'Add a reminder' })

    fireEvent.change(within(form).getByLabelText('Title'), { target: { value: ' Water the plants ' } })
    fireEvent.click(within(form).getByRole('radio', { name: 'Weekly' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Add reminder' }))
    expect(await within(form).findByRole('alert')).toHaveTextContent('Choose at least one day of the week.')
    fireEvent.click(within(form).getByRole('button', { name: 'Thu' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Mon' }))
    fireEvent.click(within(form).getByRole('button', { name: 'Add reminder' }))

    await waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/reminders')).toMatchObject({
      title: 'Water the plants', at: null, notify: 'at', repeat: { kind: 'weekly', weekdays: [0, 3] },
    }))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Bins out done' }))
    await waitFor(() => expect(screen.getByRole('checkbox', { name: 'Bins out done' })).toHaveAttribute('aria-checked', 'true'))
    expect(sentBody(fetchMock, 'POST', '/api/reminders/1/done')).toEqual({ day: '2026-11-04', done: true })
  })

  it('changes and deletes a reminder, and says why a write failed', async () => {
    const fetchMock = stubApi({
      '/api/reminders': DATA,
      'PUT /api/reminders/1': failWith(422, { detail: 'an hour before needs a time' }),
      'DELETE /api/reminders/1': { ...DATA, due: [], reminders: [] },
    })
    renderRoute('/reminders')

    fireEvent.click(await screen.findByRole('button', { name: 'Change Bins out' }))
    const form = screen.getByRole('form', { name: 'Change the reminder' })
    expect(within(form).getByLabelText('Title')).toHaveValue('Bins out')
    fireEvent.click(within(form).getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('an hour before needs a time')).toBeInTheDocument()
    expect(sentBody(fetchMock, 'PUT', '/api/reminders/1')).toMatchObject({ title: 'Bins out', repeat: { every: 2 } })

    fireEvent.click(screen.getByRole('button', { name: 'Delete Bins out' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete for good' }))
    expect(await screen.findByText(/No reminders yet/)).toBeInTheDocument()
    expect(screen.getByText('Nothing to remember today.')).toBeInTheDocument()
  })

  it('says when the reminders are not available', async () => {
    stubApi({ '/api/reminders': failWith(500, { detail: 'boom' }) })
    renderRoute('/reminders')
    expect(await screen.findByText(/Reminders are not available right now/)).toBeInTheDocument()
  })
})
