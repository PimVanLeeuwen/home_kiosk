import type { Tone } from '../components/ui/tones'
import type { AlertMessage, ServiceStatus } from './types'

export const STATUS_LABEL: Record<ServiceStatus, string> = {
  up: 'Running',
  starting: 'Starting',
  unhealthy: 'Unhealthy',
  down: 'Stopped',
  missing: 'No container',
  unknown: 'Status unknown',
}

/** A service's status as one of the hub's tones (its dot, its summary). */
export const STATUS_TONE: Record<ServiceStatus, Tone> = {
  up: 'up',
  starting: 'warn',
  unhealthy: 'warn',
  down: 'down',
  missing: 'down',
  unknown: 'muted',
}

/** A message's severity as one of the hub's tones (its dot on a timeline). */
export const SEVERITY_TONE: Record<AlertMessage['severity'], Tone> = { error: 'down', warning: 'warn', ok: 'up', info: 'accent' }
