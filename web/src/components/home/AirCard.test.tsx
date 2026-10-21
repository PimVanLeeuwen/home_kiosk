import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { Air } from '../../lib/types'
import { failWith, stubApi } from '../../test/stubApi'
import { AirCard } from './AirCard'

const at = (h: number, m: number) => new Date(2026, 9, 21, h, m).toISOString()
const history = (from: number, to: number) =>
  Array.from({ length: 97 }, (_, i) => ({ at: at(3, 0), co2: Math.round(from + ((to - from) * i) / 96) }))

const AIR: Air = {
  as_of: at(11, 17), stale: false, room: 'Living room', available: true,
  temperature: 22.9, humidity: 47, co2: 394, pm25: 2, quality: 'Good', level: 'fresh',
  outside: 10, history: history(560, 394),
}

function show(reply: unknown) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 21, 11, 18))
  stubApi({ '/api/air': reply })
  render(<MemoryRouter><AirCard /></MemoryRouter>)
}

afterEach(() => vi.useRealTimers())

describe('AirCard', () => {
  it('shows the temperature, humidity, fine dust and the sensor’s verdict', async () => {
    show(AIR)

    expect(await screen.findByText('22,9°')).toBeInTheDocument()
    expect(screen.getByText('47%')).toBeInTheDocument()
    expect(screen.getByText('Sensor says: Good')).toBeInTheDocument()
    expect(screen.getByText('Living room · outside 10°')).toBeInTheDocument()
    expect(screen.getByText('Updated 1 min ago · IKEA ALPSTUGA')).toBeInTheDocument()
  })

  it('shows CO₂ as a ring with its word, and the last 8 hours as a curve', async () => {
    show(AIR)

    expect(await screen.findByRole('img', { name: 'CO₂ 394 ppm, fresh' })).toBeInTheDocument()
    expect(screen.getByText('Fresh')).toHaveClass('text-up')
    expect(screen.getByRole('img', { name: 'CO₂ over the last 8 hours' })).toBeInTheDocument()
  })

  it.each([
    ['stuffy', 980, 'Getting stuffy', 'text-warn'],
    ['open_window', 1420, 'Open a window', 'text-down'],
  ] as const)('says %s in its colour', async (level, co2, word, className) => {
    show({ ...AIR, level, co2, history: history(600, co2) })
    expect(await screen.findByText(word)).toHaveClass(className)
    expect(screen.getByRole('img', { name: `CO₂ ${co2} ppm, ${word.toLowerCase()}` })).toBeInTheDocument()
  })

  it('leaves out what the sensor has not reported yet', async () => {
    show({ ...AIR, co2: null, level: null, pm25: null, quality: null, history: [] })

    expect(await screen.findByText('22,9°')).toBeInTheDocument()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.queryByText(/fine dust/)).toBeNull()
  })

  it('says so when the sensor is not answering, and marks stale figures', async () => {
    show({ ...AIR, available: false, stale: true })

    expect(await screen.findByText('The sensor is not answering: showing its last values.')).toBeInTheDocument()
    expect(screen.getByText('Showing the last known figures.')).toBeInTheDocument()
  })

  it('loads, then says the sensor is not available when the hub has no air data', async () => {
    show(failWith(503, { detail: 'no air data collected yet' }))

    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    expect(await screen.findByText('The air sensor is not available right now.')).toBeInTheDocument()
  })
})
