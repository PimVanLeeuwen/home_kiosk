import { BACKUP_MAX_AGE_HOURS, POOL_FULL_PCT } from './attention'
import { ahead } from './countdown'
import type { CardState } from './homeOrder'
import type { Playing } from './musicTypes'
import type { Countdowns, PhotoOfTheDay } from './pieceTypes'
import { troubled } from './outside'
import { focusOf, todayShows } from './today'
import { localDate, trainShows } from './train'
import type { AppleDevices, Briefing, DnsStats, Laundry, Nas, OutsideServices, Service, Today, Train } from './types'

/** An event starting within this many minutes counts as live on Home. */
export const SOON_MINUTES = 60

/** A countdown is a calm card while one is still ahead. */
export const countdownState = (countdowns: Countdowns | undefined, now: Date): CardState =>
  ahead(countdowns?.events, now).length > 0 ? 'quiet' : 'hidden'

/** The photo of the day shows on its own day only: yesterday's waits for this morning's read. */
export function photoState(photo: PhotoOfTheDay | undefined, now: Date): CardState {
  if (!photo?.asset || !photo.taken) return 'hidden'
  const monthDay = `${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return photo.taken.slice(5) === monthDay ? 'quiet' : 'hidden'
}

export const trainState = (train: Train | undefined, now: Date): CardState =>
  trainShows(train, now) ? 'live' : 'hidden'

export function todayState(today: Today | undefined, now: Date): CardState {
  if (!todayShows(today, now)) return 'hidden'
  const focus = focusOf(today.events, now)
  if (focus?.now) return 'now'
  return focus && focus.minutes <= SOON_MINUTES ? 'live' : 'quiet'
}

export const nowPlayingState = (playing: Playing | null): CardState => (playing ? 'live' : 'hidden')

export function laundryState(laundry: Laundry | undefined): CardState {
  if (!laundry?.showing) return 'hidden'
  return laundry.machines.some((m) => m.state === 'error') ? 'warn' : 'live'
}

export function appleState(apple: AppleDevices | undefined): CardState {
  if (!apple?.rooms.length) return 'hidden'
  return apple.rooms.some((r) => r.playing?.state === 'playing') ? 'live' : 'quiet'
}

/** An outside problem is worth a look but not something the house can fix: never more than a warning. */
export const outsideState = (outside: OutsideServices | undefined): CardState =>
  outside && troubled(outside.services).length > 0 ? 'warn' : 'quiet'

export function nasState(nas: Nas | undefined): CardState {
  if (!nas) return 'quiet'
  if (nas.disks.some((d) => d.smart === 'fail')) return 'down'
  const full = nas.storage.pools.some((p) => p.used_pct >= POOL_FULL_PCT)
  return nas.stale || full || nas.disks.some((d) => d.smart === 'warn') ? 'warn' : 'quiet'
}

export function backupsState(nas: Nas | undefined, now: Date): CardState {
  if (!nas) return 'quiet'
  const { status, at } = nas.backup
  if (status === 'fail') return 'down'
  if (status === 'unknown' || !at) return 'warn'
  return now.getTime() - new Date(at).getTime() > BACKUP_MAX_AGE_HOURS * 3_600_000 ? 'warn' : 'quiet'
}

export function servicesState(services: Service[] | undefined): CardState {
  if (!services) return 'quiet'
  if (services.some((s) => s.status === 'down' || s.status === 'missing')) return 'down'
  return services.some((s) => s.status === 'unhealthy') ? 'warn' : 'quiet'
}

/** No blocking (AdGuard not answering, or paused) lets every ad through: worth a look, never down. */
export function dnsState(dns: DnsStats | undefined): CardState {
  if (!dns) return 'quiet'
  return !dns.answering || !dns.protection ? 'warn' : 'quiet'
}

/** The morning digest on the day it was written, until 09:00 (the panel's Briefing screen too):
 * live, so it leads the morning right after the train; never the hero. */
export const briefingState = (briefing: Briefing | undefined, now: Date): CardState =>
  briefing && briefing.date === localDate(now) && now < new Date(briefing.until) ? 'live' : 'hidden'
