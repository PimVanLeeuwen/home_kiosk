import { render, screen } from '@testing-library/react'
import { RainRing } from './RainRing'
import { SunArc } from './SunArc'

const at = (minute: number) => new Date(2026, 9, 12, 10, minute).toISOString()

describe('RainRing', () => {
  it('draws a segment per five minutes, longer as the rain gets heavier', () => {
    const points = [0, 0.05, 0.4, 6].map((mm, i) => ({ at: at(i * 5), mm_per_hour: mm }))
    const { container } = render(<RainRing points={points} temperature={12.6} />)

    const ring = screen.getByRole('img', { name: 'Rain from 10:10, up to 6,0 mm/h' })
    expect(ring).toHaveTextContent('13°')
    const segments = [...container.querySelectorAll('path[d^="M"]')].slice(0, 4)
    expect(segments.map((s) => s.hasAttribute('data-wet'))).toEqual([false, false, true, true])
    // Heavier rain reaches further out; anything above 3 mm/h looks the same.
    const reach = (d: string | null) => Number(d!.split(' A')[2].split(' ')[0])
    expect(reach(segments[3].getAttribute('d'))).toBeGreaterThan(reach(segments[2].getAttribute('d')))
  })

  it('says dry, and leaves the middle empty without a temperature', () => {
    render(<RainRing points={[{ at: at(0), mm_per_hour: 0 }]} temperature={null} />)
    expect(screen.getByRole('img', { name: 'Dry for the next 2 hours' })).not.toHaveTextContent('°')
  })
})

describe('SunArc', () => {
  const rise = new Date(2026, 9, 12, 8, 0).toISOString()
  const set = new Date(2026, 9, 12, 19, 0).toISOString()

  it('puts the sun on the arc by day, highest at noon', () => {
    const { rerender } = render(<SunArc sunrise={rise} sunset={set} now={new Date(2026, 9, 12, 9, 0)} />)
    expect(screen.getByRole('img', { name: 'Sun up from 08:00 to 19:00' })).toBeInTheDocument()
    const early = Number(screen.getByTestId('sun').getAttribute('cy'))

    rerender(<SunArc sunrise={rise} sunset={set} now={new Date(2026, 9, 12, 13, 30)} />)
    expect(Number(screen.getByTestId('sun').getAttribute('cy'))).toBeLessThan(early)
  })

  it('has no sun at night', () => {
    const { rerender } = render(<SunArc sunrise={rise} sunset={set} now={new Date(2026, 9, 12, 6, 0)} />)
    expect(screen.getByRole('img', { name: 'Sunrise at 08:00' })).toBeInTheDocument()
    expect(screen.queryByTestId('sun')).toBeNull()

    rerender(<SunArc sunrise={rise} sunset={set} now={new Date(2026, 9, 12, 21, 0)} />)
    expect(screen.getByRole('img', { name: 'The sun set at 19:00' })).toBeInTheDocument()
  })
})
