import { STATUS_LABEL } from './status'
import type { Nas, Service, Site } from './types'

export interface Attention {
  level: 'warn' | 'down'
  text: string
}

/** A backup older than this counts as missed; it runs nightly. */
export const BACKUP_MAX_AGE_HOURS = 26
export const POOL_FULL_PCT = 90

/**
 * What needs looking at, worst first: failing disks and backups, stopped
 * services and sites that are down, then warnings. Drives the Home status strip.
 */
export function attentionItems(
  nas: Nas | undefined,
  services: Service[],
  now = new Date(),
  sites: Site[] = [],
): Attention[] {
  const items: Attention[] = []

  if (nas) {
    for (const disk of nas.disks) {
      if (disk.smart === 'fail') items.push({ level: 'down', text: `Disk ${disk.name} is failing` })
      if (disk.smart === 'warn') items.push({ level: 'warn', text: `Disk ${disk.name} has SMART warnings` })
    }
    for (const pool of nas.storage.pools) {
      if (pool.used_pct >= POOL_FULL_PCT)
        items.push({ level: 'warn', text: `${pool.name} ${Math.floor(pool.used_pct)}% full` })
    }
    const { status, at } = nas.backup
    if (status === 'fail') items.push({ level: 'down', text: 'Last backup failed' })
    else if (status === 'unknown' || !at) items.push({ level: 'warn', text: 'Backup status unknown' })
    else if (now.getTime() - new Date(at).getTime() > BACKUP_MAX_AGE_HOURS * 3_600_000)
      items.push({ level: 'warn', text: 'No backup in the last day' })
    if (nas.stale) items.push({ level: 'warn', text: 'NAS figures are out of date' })
  }

  for (const service of services) {
    if (service.status === 'down' || service.status === 'missing')
      items.push({ level: 'down', text: `${service.name}: ${STATUS_LABEL[service.status].toLowerCase()}` })
    if (service.status === 'unhealthy')
      items.push({ level: 'warn', text: `${service.name} is unhealthy` })
  }

  for (const site of sites) {
    if (site.up === false) items.push({ level: 'down', text: `${site.name} is down` })
  }

  return items.sort((a, b) => (a.level === b.level ? 0 : a.level === 'down' ? -1 : 1))
}
