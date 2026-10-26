import { fireEvent, render, screen } from '@testing-library/react'
import { failWith, sentBody, stubApi } from '../../test/stubApi'
import { RunningSettings } from './RunningSettings'
import { vi } from 'vitest'

describe('RunningSettings', () => {
  it('fetches the streets once, saying what that request tells Overpass', async () => {
    const fetchMock = stubApi({
      '/api/runs/streets': { fetched_at: null, counts: {} },
      'POST /api/runs/streets': { fetched_at: new Date().toISOString(), counts: { major: 40, minor: 300, path: 120, water: 6, park: 9 } },
    })
    render(<RunningSettings />)

    expect(await screen.findByText('Not fetched yet.')).toBeInTheDocument()
    expect(screen.getByText(/that request tells Overpass the area you run in/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Fetch the streets' }))

    expect(await screen.findByText(/460 streets and paths, 6 waters, 9 parks/)).toBeInTheDocument()
    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/runs/streets')).toEqual({}))
    expect(screen.getByRole('button', { name: 'Fetch them again' })).toBeInTheDocument()
  })

  it("says when Overpass could not be reached", async () => {
    stubApi({
      '/api/runs/streets': { fetched_at: null, counts: {} },
      'POST /api/runs/streets': failWith(502, { detail: "OpenStreetMap's Overpass could not be reached; try again later." }),
    })
    render(<RunningSettings />)

    fireEvent.click(await screen.findByRole('button', { name: 'Fetch the streets' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Overpass could not be reached')
  })
})
