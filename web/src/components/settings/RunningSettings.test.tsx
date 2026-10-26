import { fireEvent, render, screen } from '@testing-library/react'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { RunningSettings } from './RunningSettings'
import { vi } from 'vitest'

const HOME = { key: '52.500,3.500', home: true, runs: 40, last: '2026-10-25T07:00:00+00:00', where: 'home', fetched_at: null, counts: {} }
const AWAY = { key: '53.300,3.500', home: false, runs: 2, last: '2026-08-03T07:00:00+00:00', where: 'about 90 km north', fetched_at: null, counts: {} }

describe('RunningSettings', () => {
  it("fetches one area's streets at a time, saying what that request tells Overpass", async () => {
    const counts = { major: 40, minor: 300, path: 120, water: 6, park: 9 }
    const fetchMock = stubApi({
      '/api/runs/streets': { areas: [HOME, AWAY] },
      'POST /api/runs/streets': { areas: [{ ...HOME, fetched_at: new Date().toISOString(), counts }, AWAY] },
    })
    render(<RunningSettings />)

    expect(await screen.findByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Elsewhere, about 90 km north')).toBeInTheDocument()
    expect(screen.getAllByText('Not fetched yet.')).toHaveLength(2)
    expect(screen.getByText(/that request tells Overpass that area/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Fetch the streets: home' }))

    expect(await screen.findByText(/460 streets and paths, 6 waters, 9 parks/)).toBeInTheDocument()
    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/runs/streets')).toEqual({ area: '52.500,3.500' }))
    expect(screen.getByRole('button', { name: 'Fetch again: home' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fetch the streets: about 90 km north' })).toBeInTheDocument()
  })

  it('says when there are no runs with a route yet', async () => {
    stubApi({ '/api/runs/streets': { areas: [] } })
    render(<RunningSettings />)
    expect(await screen.findByText('No runs with a route yet.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('says when Overpass could not be reached, beside that area', async () => {
    stubApi({
      '/api/runs/streets': { areas: [HOME, AWAY] },
      'POST /api/runs/streets': failWith(502, { detail: "OpenStreetMap's Overpass could not be reached; try again later." }),
    })
    render(<RunningSettings />)

    fireEvent.click(await screen.findByRole('button', { name: 'Fetch the streets: about 90 km north' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Overpass could not be reached')
  })
})
