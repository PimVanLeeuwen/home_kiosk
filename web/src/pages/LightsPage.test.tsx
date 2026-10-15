import { act, fireEvent, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { Lights } from '../lib/types'
import { renderRoute } from '../test/renderRoute'
import { failWith, sentBody, stubApi } from '../test/stubApi'

const light = (id: string, name: string, on: boolean, brightness: number, kelvin: number | null, reachable = true) => ({
  id,
  name,
  on,
  brightness,
  kelvin,
  reachable,
})

function lights(over: { spotsOn?: boolean; lampsOn?: boolean; stale?: boolean; unreachable?: boolean } = {}): Lights {
  const spotsOn = over.spotsOn ?? true
  const lampsOn = over.lampsOn ?? true
  return {
    as_of: new Date().toISOString(),
    stale: over.stale ?? false,
    room: 'Living room',
    kelvins: [2200, 2700, 3500, 4500, 6500],
    groups: [
      {
        id: 'kitchen',
        name: 'Kitchen spots',
        kind: 'ambiance',
        on: spotsOn,
        brightness: 77,
        kelvin: 4500,
        lights: [
          light('s1', 'Keuken 1', spotsOn, 77, 4500),
          light('s2', 'Keuken 2', spotsOn, 77, 4500, !over.unreachable),
          light('s3', 'Keuken 3', spotsOn, 77, 4500),
        ],
      },
      {
        id: 'ceiling',
        name: 'Ceiling lamps',
        kind: 'white',
        on: lampsOn,
        brightness: 55,
        kelvin: null,
        lights: [light('b1', 'Plafondlamp Bank', lampsOn, 55, null), light('b2', 'Plafondlamp Tafel', lampsOn, 55, null)],
      },
    ],
  }
}

const tile = (name: string) => screen.findByRole('region', { name })

describe('LightsPage', () => {
  it('shows the two groups with their state, whites and each light', async () => {
    stubApi({ '/api/lights': lights({ lampsOn: false, unreachable: true }) })
    renderRoute('/lights')

    expect(await screen.findByText('3 of 5 on')).toBeInTheDocument()
    const kitchen = await tile('Kitchen spots')
    expect(within(kitchen).getByRole('button', { pressed: true })).toHaveTextContent('77%')
    expect(within(kitchen).getByText('Hue ambiance · 3 spots · 4500 K')).toBeInTheDocument()
    expect(within(kitchen).getByRole('radio', { name: '4500 K' })).toHaveAttribute('aria-checked', 'true')
    expect(within(kitchen).getAllByRole('radio')).toHaveLength(5)
    expect(within(kitchen).getByText('unreachable')).toBeInTheDocument()

    const ceiling = await tile('Ceiling lamps')
    expect(within(ceiling).getByRole('button', { pressed: false })).toHaveTextContent('Off')
    expect(within(ceiling).queryByRole('radio')).not.toBeInTheDocument()
    expect(within(ceiling).getAllByRole('listitem').map((li) => li.dataset.on)).toEqual(['false', 'false'])
  })

  it('switches a group and shows what the bridge answers', async () => {
    const fetchMock = stubApi({
      '/api/lights': lights(),
      'PUT /api/lights/ceiling': { ...lights({ lampsOn: false }), as_of: new Date(Date.now() + 1000).toISOString() },
    })
    renderRoute('/lights')

    fireEvent.click(within(await tile('Ceiling lamps')).getByRole('button', { pressed: true }))

    expect(await within(await tile('Ceiling lamps')).findByRole('button', { pressed: false })).toHaveTextContent('Off')
    expect(sentBody(fetchMock, 'PUT', '/api/lights/ceiling')).toEqual({ on: false })
    expect(screen.getByText('3 of 5 on')).toBeInTheDocument()
  })

  it('picks a white for the spots', async () => {
    const fetchMock = stubApi({ '/api/lights': lights(), 'PUT /api/lights/kitchen': lights() })
    renderRoute('/lights')

    fireEvent.click(within(await tile('Kitchen spots')).getByRole('radio', { name: '2700 K' }))

    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', '/api/lights/kitchen')).toEqual({ kelvin: 2700 }))
  })

  it('sends a brightness once the slider rests', async () => {
    const fetchMock = stubApi({ '/api/lights': lights(), 'PUT /api/lights/kitchen': lights() })
    renderRoute('/lights')
    const slider = within(await tile('Kitchen spots')).getByRole('slider', { name: 'Kitchen spots brightness' })

    vi.useFakeTimers()
    try {
      fireEvent.change(slider, { target: { value: '50' } })
      fireEvent.change(slider, { target: { value: '30' } })
      expect(within(screen.getByRole('region', { name: 'Kitchen spots' })).getByRole('button', { pressed: true })).toHaveTextContent('30%')
      await act(() => vi.advanceTimersByTimeAsync(350))
    } finally {
      vi.useRealTimers()
    }

    await vi.waitFor(() => expect(sentBody(fetchMock, 'PUT', '/api/lights/kitchen')).toEqual({ brightness: 30 }))
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1)
  })

  it('switches the whole room off, or on when all are off', async () => {
    const fetchMock = stubApi({ '/api/lights': lights(), 'POST /api/lights/room': lights() })
    renderRoute('/lights')

    fireEvent.click(await screen.findByRole('button', { name: 'All off' }))
    await vi.waitFor(() => expect(sentBody(fetchMock, 'POST', '/api/lights/room')).toEqual({ on: false }))
  })

  it('says why a change failed', async () => {
    stubApi({ '/api/lights': lights(), 'PUT /api/lights/kitchen': failWith(502, { detail: 'The bridge is not reachable' }) })
    renderRoute('/lights')

    fireEvent.click(within(await tile('Kitchen spots')).getByRole('button', { pressed: true }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The bridge is not reachable')
  })

  it('shows the last known state with the controls off while the bridge is away', async () => {
    stubApi({ '/api/lights': lights({ stale: true }) })
    renderRoute('/lights')

    expect(await screen.findByText(/Last known state/)).toBeInTheDocument()
    expect(within(await tile('Kitchen spots')).getByRole('slider')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'All off' })).toBeDisabled()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('holds a switch while the bridge still answers with the old state, then follows it', async () => {
    let reported = lights()
    stubApi({ '/api/lights': () => reported, 'PUT /api/lights/ceiling': () => reported })
    renderRoute('/lights')
    const ceiling = await tile('Ceiling lamps')

    fireEvent.click(within(ceiling).getByRole('button', { pressed: true }))

    // The bridge's first answer is still "on": the tile stays off, no flip back.
    expect(within(ceiling).getByRole('button', { pressed: false })).toHaveTextContent('Off')
    expect(screen.getByText('3 of 5 on')).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.getByRole('region', { name: 'Ceiling lamps' }).closest('[aria-busy]')).toHaveAttribute('aria-busy', 'true'))

    // One lamp reports off, the other not yet: still held.
    reported = lights()
    reported.groups[1].lights[0].on = false
    await act(() => new Promise((r) => setTimeout(r, 2_100)))
    expect(within(ceiling).getByRole('button', { pressed: false })).toHaveTextContent('Off')

    // Both off: confirmed, and the hold lets go.
    reported = lights({ lampsOn: false })
    await vi.waitFor(() => expect(screen.getByRole('region', { name: 'Ceiling lamps' }).closest('[aria-busy]')).toHaveAttribute('aria-busy', 'false'), {
      timeout: 3_000,
    })
    expect(within(ceiling).getByRole('button', { pressed: false })).toHaveTextContent('Off')
  }, 10_000)

  it('keeps the dragged level after letting go until the bridge reports it', async () => {
    stubApi({ '/api/lights': lights(), 'PUT /api/lights/kitchen': lights() })
    renderRoute('/lights')
    const kitchen = await tile('Kitchen spots')

    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      fireEvent.change(within(kitchen).getByRole('slider'), { target: { value: '30' } })
      await act(() => vi.advanceTimersByTimeAsync(400))
    } finally {
      vi.useRealTimers()
    }

    // The answer still says 77, but the tile shows the asked 30, not a jump back.
    await vi.waitFor(() => expect(within(kitchen).getByRole('slider')).toHaveValue('30'))
    expect(within(kitchen).getByRole('button', { pressed: true })).toHaveTextContent('30%')
  })

  it('shows what the bridge has once a change is not confirmed in time', async () => {
    stubApi({ '/api/lights': lights(), 'PUT /api/lights/ceiling': lights() })
    renderRoute('/lights')
    const ceiling = await tile('Ceiling lamps')

    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    try {
      fireEvent.click(within(ceiling).getByRole('button', { pressed: true }))
      expect(within(ceiling).getByRole('button', { pressed: false })).toHaveTextContent('Off')
      await act(() => vi.advanceTimersByTimeAsync(5_100))
    } finally {
      vi.useRealTimers()
    }

    expect(await within(ceiling).findByRole('button', { pressed: true })).toHaveTextContent('55%')
  })

  it('explains when the lights are not read yet', async () => {
    stubApi({})
    renderRoute('/lights')

    expect(await screen.findByRole('alert')).toHaveTextContent('The lights are not available yet')
  })
})
