import { containerStatus } from './containers'

it('maps container state and health to a status dot', () => {
  expect(containerStatus({ state: 'running', health: null })).toBe('up')
  expect(containerStatus({ state: 'running', health: 'healthy' })).toBe('up')
  expect(containerStatus({ state: 'running', health: 'unhealthy' })).toBe('unhealthy')
  expect(containerStatus({ state: 'running', health: 'starting' })).toBe('starting')
  expect(containerStatus({ state: 'exited', health: null })).toBe('down')
})
