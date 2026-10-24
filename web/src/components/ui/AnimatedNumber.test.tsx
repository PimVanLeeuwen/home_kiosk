import { act, render, screen } from '@testing-library/react'
import { AnimatedNumber } from './AnimatedNumber'

const motion = (allowed: boolean) =>
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: allowed && query.includes('no-preference'), media: query }))

describe('AnimatedNumber', () => {
  afterEach(() => vi.useRealTimers())

  it('shows the first value at once and moves to a new one', () => {
    // Our own clock for the frames, so a slow runner cannot outlast the ease.
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] })
    motion(true)
    const { rerender } = render(<AnimatedNumber value={10} format={(n) => `${Math.round(n)}%`} />)
    expect(screen.getByText('10%')).toBeInTheDocument()

    rerender(<AnimatedNumber value={90} format={(n) => `${Math.round(n)}%`} />)
    // Not there yet straight after the change, there after the ease.
    expect(screen.queryByText('90%')).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByText('90%')).not.toBeInTheDocument()
    act(() => vi.advanceTimersByTime(500))
    expect(screen.getByText('90%')).toBeInTheDocument()
  })

  it('jumps with reduced motion', () => {
    motion(false)
    const { rerender } = render(<AnimatedNumber value={1} />)
    rerender(<AnimatedNumber value={7} />)
    expect(screen.getByText('7')).toBeInTheDocument()
  })
})
