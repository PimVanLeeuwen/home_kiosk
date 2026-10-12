import { render, screen } from '@testing-library/react'
import { ArcGauge } from './ArcGauge'
import { BarStrip } from './BarStrip'
import { FlowLine } from './FlowLine'
import { GlassTile } from './GlassTile'
import { GlowArea } from './GlowArea'
import { GlowDot } from './GlowDot'
import { MiniSparkline } from './MiniSparkline'
import { Pill } from './Pill'
import { Seal } from './Seal'

describe('ArcGauge', () => {
  it('is a meter with the figure, clamped to 0 to 100', () => {
    render(<ArcGauge pct={104.6} label="volume2">volume2 · 5,5 of 6,0 TB</ArcGauge>)

    const meter = screen.getByRole('meter', { name: 'volume2' })
    expect(meter).toHaveAttribute('aria-valuenow', '100')
    expect(meter).toHaveTextContent('100%')
    expect(screen.getByText('volume2 · 5,5 of 6,0 TB')).toBeInTheDocument()
  })

  it('marks the alert threshold, and turns the arc end amber past it', () => {
    const { container, rerender } = render(<ArcGauge pct={68} alertAt={90} label="v" />)
    expect(screen.getByTestId('alert-mark')).toBeInTheDocument()
    const end = () => container.querySelectorAll('stop')[2].getAttribute('stop-color')
    expect(end()).not.toBe('var(--color-warn)')

    rerender(<ArcGauge pct={92} alertAt={90} label="v" />)
    expect(end()).toBe('var(--color-warn)')
  })

  it('draws no arc at zero, and no mark without a threshold', () => {
    const { container } = render(<ArcGauge pct={0} label="empty" />)

    expect(container.querySelectorAll('path')).toHaveLength(1) // the track only
    expect(screen.queryByTestId('alert-mark')).not.toBeInTheDocument()
  })

  it('keeps gradient ids apart when two gauges share a page', () => {
    const { container } = render(
      <>
        <ArcGauge pct={10} label="a" />
        <ArcGauge pct={20} label="b" />
      </>,
    )
    const ids = [...container.querySelectorAll('linearGradient')].map((g) => g.id)
    expect(new Set(ids).size).toBe(2)
  })
})

describe('BarStrip', () => {
  it('draws a bar per value, the marked one and the last in their own colour', () => {
    const { container } = render(
      <BarStrip values={[70, 72, 94, 71]} label="Backup durations, 4 nights" marks={{ 2: 'warn' }} start="4 nights" markLabel="slow" end="last night" />,
    )

    expect(screen.getByRole('img', { name: 'Backup durations, 4 nights' })).toBeInTheDocument()
    const fills = [...container.querySelectorAll('rect')].map((r) => r.getAttribute('fill'))
    expect(fills).toHaveLength(4)
    expect(fills[2]).toBe('var(--color-warn)')
    expect(fills[3]).toBe('var(--color-up)')
    expect(fills[0]).toMatch(/^url\(#/)
    expect(screen.getByText('slow')).toBeInTheDocument()
    expect(screen.getByText('last night')).toBeInTheDocument()
  })

  it('puts the label under the bar it is given', () => {
    render(<BarStrip values={[70, 94, 71, 72]} label="n" marks={{ 1: 'warn', 2: 'down' }} markLabel="failed" markAt={2} end="last night" />)
    expect(screen.getByText('failed')).toHaveAttribute('fill', 'var(--color-down)')
    expect(screen.getByText('last night')).toBeInTheDocument()
  })

  it('shares the end words when the label belongs to the newest bar', () => {
    render(<BarStrip values={[70, 94, 71]} label="n" marks={{ 2: 'down' }} markLabel="failed" markAt={2} end="last night" />)
    expect(screen.getByText('last night: failed')).toHaveAttribute('fill', 'var(--color-down)')
    expect(screen.queryByText('failed')).not.toBeInTheDocument()
  })

  it('renders nothing without values', () => {
    const { container } = render(<BarStrip values={[]} label="none" />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('charts', () => {
  it('needs two points for a line', () => {
    const { container } = render(
      <>
        <GlowArea values={[1]} label="area" />
        <MiniSparkline values={[1]} label="spark" />
      </>,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('labels the area chart and the sparkline', () => {
    render(
      <>
        <GlowArea values={[1, 3, 2]} label="Portfolio value, last 30 days" tone="up" />
        <MiniSparkline values={[8, 12, 9]} label="CPU, last 24 hours" />
      </>,
    )
    expect(screen.getByRole('img', { name: 'Portfolio value, last 30 days' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'CPU, last 24 hours' })).toBeInTheDocument()
  })

  it('marks the peak, draws a second line and keeps a fixed scale', () => {
    const { container } = render(<GlowArea values={[10, 50, 20]} label="cpu" min={0} max={100} peak secondary={[5, 5, 5]} />)
    expect(container.querySelector('[data-testid="peak"]')).not.toBeNull()
    expect(container.querySelector('[data-testid="secondary"]')).not.toBeNull()
    // On a 0 to 100 scale, 50 sits halfway down the plot (12 + 0.5 * 94).
    expect(container.querySelector('polyline')?.getAttribute('points')).toContain('300.0,59.0')
  })

  it('takes a colour of its own', () => {
    const { container } = render(<GlowArea values={[1, 2]} label="t" color="#7cc4ff" />)
    expect(container.querySelector('polyline')).toHaveAttribute('stroke', '#7cc4ff')
  })

  it('draws a flat series in the middle instead of failing', () => {
    const { container } = render(<MiniSparkline values={[5, 5, 5]} label="flat" />)
    expect(container.querySelector('polyline')?.getAttribute('points')).not.toMatch(/NaN/)
  })
})

describe('small pieces', () => {
  it('a glass tile shows its label, figure and extra', () => {
    render(
      <GlassTile label="CPU" value="11%">
        <span>spark</span>
      </GlassTile>,
    )
    expect(screen.getByText('CPU')).toBeInTheDocument()
    expect(screen.getByText('11%')).toBeInTheDocument()
    expect(screen.getByText('spark')).toBeInTheDocument()
  })

  it('a glow dot is decoration unless it has a label', () => {
    const { container } = render(<GlowDot tone="up" />)
    expect(container.firstChild).toHaveAttribute('aria-hidden', 'true')

    render(<GlowDot tone="warn" halo label="Needs a look" />)
    expect(screen.getByRole('img', { name: 'Needs a look' })).toHaveClass('motion-safe:animate-halo')
  })

  it('a seal says whether it passed', () => {
    render(
      <>
        <Seal ok label="Backup succeeded" />
        <Seal ok={false} label="Backup failed" />
      </>,
    )
    expect(screen.getByRole('img', { name: 'Backup succeeded' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Backup failed' })).toBeInTheDocument()
  })

  it('a flow line names its route and only moves while it works', () => {
    const { container, rerender } = render(<FlowLine from="NAS" to="Hetzner · encrypted" />)
    expect(screen.getByRole('img', { name: 'NAS to Hetzner · encrypted' })).toBeInTheDocument()
    expect(container.querySelector('i')).toHaveClass('motion-safe:animate-flow')

    rerender(<FlowLine from="NAS" to="Hetzner" ok={false} />)
    expect(container.querySelector('i')).toBeNull()
  })

  it('a pill shows its words', () => {
    render(<Pill tone="up">All safe</Pill>)
    expect(screen.getByText('All safe')).toHaveClass('text-up')
  })
})
