import { render, screen } from '@testing-library/react'
import type { ServiceStatus } from '../lib/types'
import { StatusDot } from './StatusDot'

const dot = (status: ServiceStatus) => {
  const { container } = render(<StatusDot status={status} />)
  return container.firstChild as HTMLElement
}

describe('StatusDot', () => {
  it('names its status for screen readers and on hover', () => {
    expect(dot('unhealthy')).toHaveAttribute('title', 'Unhealthy')
    expect(screen.getByText('Unhealthy')).toHaveClass('sr-only')
  })

  it.each<ServiceStatus>(['unhealthy', 'down', 'missing'])('pulses slowly when %s', (status) => {
    expect(dot(status)).toHaveClass('motion-safe:animate-halo')
  })

  it.each<ServiceStatus>(['up', 'starting', 'unknown'])('stays still when %s', (status) => {
    expect(dot(status)).not.toHaveClass('motion-safe:animate-halo')
  })

  it('glows in its colour, except when unknown', () => {
    expect(dot('down').style.getPropertyValue('--glow')).toBe('var(--color-down)')
    expect(dot('unknown').className).not.toMatch(/shadow-/)
  })
})
