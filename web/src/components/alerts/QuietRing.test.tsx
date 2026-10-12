import { render, screen } from '@testing-library/react'
import { QuietRing } from './QuietRing'

const at = (h: number) => new Date(2026, 9, 12, h, 0)

describe('QuietRing', () => {
  it('lights the quiet span across midnight', () => {
    render(<QuietRing start="23:00" end="07:00" enabled now={at(12)} />)
    const ring = screen.getByRole('img', { name: 'Quiet from 23:00 to 07:00' })
    expect(ring).toHaveTextContent('23–07')
    // 8 of 24 hours, starting at 23 of 24.
    const span = screen.getByTestId('quiet-span')
    const c = 2 * Math.PI * 38
    expect(Number(span.getAttribute('stroke-dasharray')!.split(' ')[0])).toBeCloseTo((8 / 24) * c, 1)
    expect(Number(span.getAttribute('stroke-dashoffset'))).toBeCloseTo((-23 / 24) * c, 1)
  })

  it('says off and lights nothing when quiet hours are off', () => {
    render(<QuietRing start="23:00" end="07:00" enabled={false} now={at(12)} />)
    expect(screen.getByRole('img', { name: 'Quiet hours off' })).toHaveTextContent('off')
    expect(screen.queryByTestId('quiet-span')).toBeNull()
  })
})
