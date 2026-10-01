import type { ContainerLoad, ServiceStatus } from './types'

/** A container's state as a status dot, like the service tiles. */
export function containerStatus(c: Pick<ContainerLoad, 'state' | 'health'>): ServiceStatus {
  if (c.state !== 'running') return 'down'
  if (c.health === 'unhealthy' || c.health === 'starting') return c.health
  return 'up'
}
