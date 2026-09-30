import type { ServiceStatus } from './types'

export const STATUS_LABEL: Record<ServiceStatus, string> = {
  up: 'Running',
  starting: 'Starting',
  unhealthy: 'Unhealthy',
  down: 'Stopped',
  missing: 'No container',
  unknown: 'Status unknown',
}
