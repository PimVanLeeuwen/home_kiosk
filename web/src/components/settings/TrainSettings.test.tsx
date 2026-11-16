import { fireEvent, render, screen, within } from '@testing-library/react'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { TrainSettings } from './TrainSettings'

const day = (name: string) => screen.findByRole('button', { name })

describe('TrainSettings', () => {
  it('shows the train days, every weekday by default', async () => {
    stubApi({ '/api/settings/train': { days: [0, 1, 2, 3, 4] } })
    render(<TrainSettings />)

    expect(await day('Mon')).toHaveAttribute('aria-pressed', 'true')
    expect(await day('Fri')).toHaveAttribute('aria-pressed', 'true')
    expect(await day('Sat')).toHaveAttribute('aria-pressed', 'false')
  })

  it('takes a day off and shows what the hub saved', async () => {
    const fetchMock = stubApi({
      '/api/settings/train': { days: [0, 1, 2, 3, 4] },
      'PUT /api/settings/train': { days: [0, 1, 3, 4] },
    })
    render(<TrainSettings />)

    fireEvent.click(await day('Wed'))

    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Wed' })).toHaveAttribute('aria-pressed', 'false'))
    expect(sentBody(fetchMock, 'PUT', '/api/settings/train')).toEqual({ days: [0, 1, 3, 4] })
  })

  it('adds a weekend day', async () => {
    const fetchMock = stubApi({ '/api/settings/train': { days: [0] }, 'PUT /api/settings/train': { days: [0, 5] } })
    render(<TrainSettings />)

    fireEvent.click(await day('Sat'))

    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Sat' })).toHaveAttribute('aria-pressed', 'true'))
    expect(sentBody(fetchMock, 'PUT', '/api/settings/train')).toEqual({ days: [0, 5] })
  })

  it('says when no day is picked, and why a change did not save', async () => {
    stubApi({ '/api/settings/train': { days: [] }, 'PUT /api/settings/train': failWith(422, { detail: 'Bad day.' }) })
    render(<TrainSettings />)

    expect(await screen.findByText(/No train days/)).toBeInTheDocument()
    fireEvent.click(await day('Mon'))
    expect(within(await screen.findByRole('alert')).getByText(/Bad day/)).toBeInTheDocument()
  })
})
