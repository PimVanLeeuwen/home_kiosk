import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { PageHeader } from '../PageHeader'
import { AttentionRow, HealthyLine } from './AttentionRow'
import { Card } from './Card'
import { Cell, CellGrid } from './CellGrid'
import { Headline } from './Headline'
import { Sparkline } from './Sparkline'

const inRouter = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>)

describe('the neo-minimal surfaces (M38)', () => {
  it('draws a card flat, with a hairline edge and no sheen', () => {
    inRouter(<Card title="NAS">x</Card>)
    const card = screen.getByRole('region', { name: 'NAS' })
    expect(card).toHaveClass('bg-card', 'border-line-soft')
    expect(card.className).not.toMatch(/bg-linear|from-white/)
  })

  it('cuts a CellGrid into cells that each draw their own hairline', () => {
    inRouter(
      <CellGrid label="The NAS at a glance" columns={4}>
        <Cell title="CPU" link={{ to: '/house/nas', label: 'NAS' }}>
          17%
        </Cell>
        <Cell span={2}>bare</Cell>
      </CellGrid>,
    )
    const grid = screen.getByRole('region', { name: 'The NAS at a glance' })
    expect(grid).toHaveClass('grid', 'gap-px', 'grid-cols-2', 'xl:grid-cols-4')
    const cpu = screen.getByRole('group', { name: 'CPU' })
    expect(cpu.className).toContain('shadow-[0_0_0_1px_var(--color-line-soft)]')
    expect(screen.getByRole('link', { name: 'NAS →' })).toHaveAttribute('href', '/house/nas')
    expect(screen.getByText('bare')).toHaveClass('col-span-full', 'sm:col-span-2')
    expect(screen.getByText('bare')).not.toHaveAttribute('role')
  })

  it('draws a sparkline as a line over a fading wash, each with its own gradient', () => {
    const { container } = render(
      <>
        <Sparkline values={[1, 3, 2]} label="CPU, last hours" />
        <Sparkline values={[2, 2, 5]} label="Memory, last hours" tone="up" />
      </>,
    )
    expect(screen.getByRole('img', { name: 'CPU, last hours' }).querySelectorAll('path')).toHaveLength(2)
    const ids = [...container.querySelectorAll('linearGradient')].map((g) => g.id)
    expect(new Set(ids).size).toBe(2)
    expect(screen.getByRole('img', { name: 'Memory, last hours' }).querySelector('path')).toHaveAttribute('fill', `url(#${ids[1]})`)
  })

  it('draws no sparkline from fewer than two values', () => {
    render(<Sparkline values={[4]} label="CPU" />)
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('gives a page title the fading headline, and a greeting its two lines', () => {
    render(<PageHeader title="Docker" />)
    expect(screen.getByRole('heading', { level: 1, name: 'Docker' })).toHaveClass('fade-text', 'md:text-display')

    render(<Headline lines={['Good evening.', 'The house is quiet.']} eyebrow="Friday" lead="Everything is running." />)
    const greeting = screen.getByRole('heading', { level: 1, name: /Good evening/ })
    expect(greeting).toHaveTextContent('Good evening.The house is quiet.')
    expect(greeting.querySelector('br')).not.toBeNull()
    expect(screen.getByText('Everything is running.')).toBeInTheDocument()
  })

  it('shows what needs a look with its tone and the way to it', () => {
    inRouter(
      <AttentionRow tone="warn" title="TransIP reports a problem" detail="Since Tue 10 Nov" action={{ to: '/outside', label: 'Outside' }} />,
    )
    const row = screen.getByText('TransIP reports a problem').closest('[data-tone]')
    expect(row).toHaveAttribute('data-tone', 'warn')
    expect(row).toHaveClass('border-warn/30')
    const link = screen.getByRole('link', { name: 'Outside' })
    expect(link).toHaveAttribute('href', '/outside')
    // A target to tap: 40px with a mouse, 44px on touch.
    expect(link).toHaveClass('min-h-10', 'pointer-coarse:min-h-11')
  })

  it('folds everything healthy into one line', () => {
    inRouter(<HealthyLine link={{ to: '/house/docker', label: 'Docker' }}>45 containers running, 4 volumes fine</HealthyLine>)
    expect(screen.getByText('45 containers running, 4 volumes fine')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Docker →' })).toHaveClass('hit')
  })
})
