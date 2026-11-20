import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { ArcGauge } from './ArcGauge'
import { BarMeter } from './BarMeter'
import { BarStrip } from './BarStrip'
import { Card, Surface } from './Card'
import { markLeft } from './markLeft'
import { FlowLine } from './FlowLine'
import { GlassTile } from './GlassTile'
import { GlowArea } from './GlowArea'
import { GlowDot } from './GlowDot'
import { MiniSparkline } from './MiniSparkline'
import { Pill } from './Pill'
import { Ring } from './Ring'
import { RingMeter } from './RingMeter'
import { RunDots } from './RunDots'
import { Seal } from './Seal'
import { Switch } from './Switch'
import { iconButtonClass } from './buttonStyles'
import { Tag } from './Tag'

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
    expect(screen.getByText('failed')).toHaveAttribute('data-tone', 'down')
    expect(screen.getByText('last night')).toBeInTheDocument()
  })

  it('shares the end words when the label belongs to the newest bar', () => {
    render(<BarStrip values={[70, 94, 71]} label="n" marks={{ 2: 'down' }} markLabel="failed" markAt={2} end="last night" />)
    expect(screen.getByText('last night: failed')).toHaveAttribute('data-tone', 'down')
    expect(screen.queryByText('failed')).not.toBeInTheDocument()
  })

  it('keeps the label clear of the end words', () => {
    // A 300 px row, "30 nights" 60 px wide on the left, "last night" 60 px on the right.
    expect(markLeft(150, 80, 60, 60, 300)).toBe(150) // in the middle: right under its bar
    expect(markLeft(15, 80, 60, 60, 300)).toBe(60 + 8 + 40) // near the start: just after it
    expect(markLeft(290, 80, 60, 60, 300)).toBe(300 - 60 - 8 - 40) // near the end: just before it
    expect(markLeft(15, 80, 0, 0, 300)).toBe(40) // no end words: only kept inside the row
    expect(markLeft(150, 200, 60, 60, 300)).toBeNull() // no room at all: left out
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

describe('RingMeter', () => {
  it('is a meter with its figure and tone, empty at zero', () => {
    const { container, rerender } = render(<RingMeter pct={64} tone="warn" label="Battery" caption="battery" />)
    const ring = screen.getByRole('meter', { name: 'Battery' })
    expect(ring).toHaveAttribute('aria-valuenow', '64')
    expect(ring).toHaveAttribute('data-tone', 'warn')
    expect(ring).toHaveTextContent('64%battery')
    expect(container.querySelectorAll('circle')).toHaveLength(2)

    rerender(<RingMeter pct={0} tone="down" label="Battery" />)
    expect(container.querySelectorAll('circle')).toHaveLength(1)
  })
})

describe('RunDots', () => {
  it('draws a dot per run oldest first, the newest lit and failed ones red', () => {
    render(<RunDots runs={[{ ok: false }, { ok: true }, { ok: true }]} label="runs" />)
    const dots = [...screen.getByRole('img', { name: 'runs' }).querySelectorAll('i')]
    expect(dots.map((d) => d.getAttribute('data-ok'))).toEqual(['true', 'true', 'false'])
    expect(dots[2]).toHaveClass('bg-down')
    expect(dots[0]).toHaveClass('bg-up/55')
  })
})

describe('Card', () => {
  it('has a sentence-case title, and on the right a note, then the pill, then the link', () => {
    render(
      <MemoryRouter>
        <Card title="Last night" note="Hetzner · encrypted" actions={<Pill tone="up">All safe</Pill>} link={{ to: '/backups', label: 'Details' }}>
          body
        </Card>
      </MemoryRouter>,
    )

    const title = screen.getByRole('heading', { name: 'Last night' })
    expect(title).not.toHaveClass('eyebrow')
    const right = title.nextElementSibling!
    expect([...right.children].map((c) => c.textContent)).toEqual(['Hetzner · encrypted', 'All safe', 'Details →'])
    expect(right.firstElementChild).toHaveClass('text-faint')
  })

  it("gives its link a hit area, as small links are hard to tap", () => {
    render(
      <MemoryRouter>
        <Card title="Weather" link={{ to: '/weather', label: 'Week and radar' }}>body</Card>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: /Week and radar/ })).toHaveClass('hit')
  })
})

describe('tap targets', () => {
  it('gives a switch a hit area beyond its 20px', () => {
    render(<Switch checked={false} onChange={() => {}} label="Show forks" />)
    expect(screen.getByRole('switch', { name: 'Show forks' })).toHaveClass('hit')
  })

  it('grows icon buttons to 44px on touch, as they sit too close for hit areas', () => {
    expect(iconButtonClass.split(' ')).toEqual(expect.arrayContaining(['size-8', 'pointer-coarse:size-11']))
  })
})

describe('Surface', () => {
  it('takes its colours from its look and its padding from a name', () => {
    render(
      <>
        <Surface look="down" padding="compact">problem</Surface>
        <MemoryRouter>
          <Card title="Revenue" padding="chart">chart</Card>
        </MemoryRouter>
      </>,
    )

    const problem = screen.getByText('problem')
    expect(problem).toHaveAttribute('data-look', 'down')
    expect(problem).toHaveClass('border-down/40', 'p-3')
    expect(problem).not.toHaveClass('border-line-soft')
    const card = screen.getByRole('region', { name: 'Revenue' })
    expect(card).toHaveClass('pt-5')
    expect(card).not.toHaveClass('py-5')
  })
})

describe('BarMeter', () => {
  it('fills in violet by default and in a state colour when given one', () => {
    render(
      <>
        <BarMeter label="volume1" value="40%" pct={40} />
        <BarMeter label="volume2" value="99%" pct={140} tone="down" />
      </>,
    )

    expect(screen.getByRole('meter', { name: 'volume1' })).toHaveAttribute('data-tone', 'accent')
    const full = screen.getByRole('meter', { name: 'volume2' })
    expect(full.firstElementChild).toHaveClass('bg-down')
    expect(full.firstElementChild).toHaveStyle({ width: '100%' })
  })
})

describe('Ring', () => {
  it('draws a clamped arc from its start, and no arc at nothing', () => {
    const { container } = render(
      <>
        <Ring data-testid="full" box={100} r={40} stroke={6} color="red" fraction={1.4} start={0.25} />
        <Ring data-testid="empty" box={100} r={40} stroke={6} color="red" fraction={0} />
      </>,
    )

    const c = 2 * Math.PI * 40
    const arc = screen.getByTestId('full').querySelector('[data-arc]')!
    expect(Number(arc.getAttribute('stroke-dasharray')!.split(' ')[0])).toBeCloseTo(c, 1)
    expect(Number(arc.getAttribute('stroke-dashoffset'))).toBeCloseTo(-0.25 * c, 1)
    expect(screen.getByTestId('empty').querySelector('[data-arc]')).toBeNull()
    expect(container.querySelectorAll('circle[stroke="var(--color-track)"]')).toHaveLength(2)
  })
})

describe('GlowDot', () => {
  it('takes a tone or a colour of its own, a size, and names itself when asked', () => {
    render(
      <>
        <GlowDot tone="down" size="lg" label="Failing" />
        <GlowDot color="#8cc4ff" size="sm" text="Tech" />
        <GlowDot tone="muted" title="Not checked" />
      </>,
    )

    const failing = screen.getByRole('img', { name: 'Failing' })
    expect(failing).toHaveAttribute('data-tone', 'down')
    expect(failing).toHaveClass('size-[9px]')
    expect(failing.className).toMatch(/shadow-/)
    const tech = screen.getByTitle('Tech')
    expect(tech).toHaveStyle({ backgroundColor: '#8cc4ff' })
    expect(within(tech).getByText('Tech')).toHaveClass('sr-only')
    const quiet = screen.getByTitle('Not checked')
    expect(quiet).toHaveAttribute('aria-hidden', 'true')
    expect(quiet.className).not.toMatch(/shadow-/)
  })

  it('stays plain in a dense row, an empty slot dimmer than a muted dot', () => {
    render(
      <>
        <GlowDot tone="up" flat title="sonarr" />
        <GlowDot tone="down" flat halo title="radarr" />
        <GlowDot flat title="a link" />
      </>,
    )

    expect(screen.getByTitle('sonarr').className).not.toMatch(/shadow-/)
    expect(screen.getByTitle('radarr')).toHaveClass('motion-safe:animate-halo')
    expect(screen.getByTitle('a link')).toHaveStyle({ backgroundColor: 'rgb(255 255 255 / 0.14)' })
  })
})

describe('Tag', () => {
  it('comes tinted, outlined or glass, in a tone or a colour of its own', () => {
    render(
      <>
        <Tag tone="down" size="micro" caps>Error</Tag>
        <Tag variant="outline" tone="accent">Relay</Tag>
        <Tag variant="glass">Fork</Tag>
        <Tag variant="glass" mono>NVDA</Tag>
        <Tag colour={{ bg: '#123', fg: '#8cc4ff' }}>Tech</Tag>
        <Tag colour="#7cc4ff">SQLite</Tag>
      </>,
    )

    expect(screen.getByText('Error')).toHaveAttribute('data-tone', 'down')
    expect(screen.getByText('Error')).toHaveClass('text-down', 'eyebrow', 'text-label')
    expect(screen.getByText('Relay')).toHaveClass('border', 'text-accent-fg')
    expect(screen.getByText('Fork')).toHaveClass('bg-glass', 'text-muted')
    expect(screen.getByText('NVDA')).toHaveClass('font-mono', 'text-fg')
    expect(screen.getByText('Tech')).toHaveStyle({ color: '#8cc4ff' })
    expect(screen.getByText('SQLite')).toHaveStyle({ color: '#7cc4ff' })
    expect(screen.getByText('SQLite')).not.toHaveAttribute('data-tone')
  })
})
