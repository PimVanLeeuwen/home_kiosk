import { fireEvent, render, screen, within } from '@testing-library/react'
import type { CalendarInfo } from '../../lib/types'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { CalendarsEditor } from './CalendarsEditor'

const CALS: CalendarInfo[] = [
  { id: 'work-id', name: 'Work', color: '#ff8d28', kind: 'icloud', shown: true },
  { id: 'gewis-id', name: 'GEWIS Activiteiten', color: '#ff6352', kind: 'subscribed', shown: true },
]

describe('CalendarsEditor', () => {
  it('lists the calendars with their kind and switch', async () => {
    stubApi({ '/api/settings/calendars': CALS })
    render(<CalendarsEditor />)

    expect(await screen.findByRole('switch', { name: 'Show Work' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('Subscription')).toBeInTheDocument()
  })

  it('switches a calendar off and shows what the hub saved', async () => {
    const fetchMock = stubApi({
      '/api/settings/calendars': CALS,
      'PUT /api/settings/calendars/gewis-id': [CALS[0], { ...CALS[1], shown: false }],
    })
    render(<CalendarsEditor />)

    fireEvent.click(await screen.findByRole('switch', { name: 'Show GEWIS Activiteiten' }))

    await vi.waitFor(() => expect(screen.getByRole('switch', { name: 'Show GEWIS Activiteiten' })).toHaveAttribute('aria-checked', 'false'))
    expect(sentBody(fetchMock, 'PUT', '/api/settings/calendars/gewis-id')).toEqual({ shown: false })
  })

  it('says why a switch did not save', async () => {
    stubApi({ '/api/settings/calendars': CALS, 'PUT /api/settings/calendars/work-id': failWith(404, { detail: 'No such calendar.' }) })
    render(<CalendarsEditor />)

    fireEvent.click(await screen.findByRole('switch', { name: 'Show Work' }))

    expect(within(await screen.findByRole('alert')).getByText(/No such calendar/)).toBeInTheDocument()
  })

  it('explains an empty list, and an unavailable one', async () => {
    stubApi({ '/api/settings/calendars': [] })
    render(<CalendarsEditor />)
    expect(await screen.findByText(/No calendars yet/)).toBeInTheDocument()
  })
})
