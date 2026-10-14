import { attentionItems } from './attention'
import type { Nas, Service } from './types'

const NOW = new Date('2026-09-30T20:00:00+02:00')

const nas = (over: Partial<Nas> = {}): Nas => ({
  as_of: '2026-09-30T19:59:00+02:00',
  stale: false,
  host: 'dev-minotaur',
  storage: {
    used_pct: 60,
    pools: [{ name: 'volume1', used_bytes: 1, total_bytes: 10, used_pct: 16, free_bytes: 9 }],
  },
  cpu_pct: 11,
  ram_pct: 24,
  cpu_temp_c: 44,
  containers: { running: 37, total: 37 },
  disks: [{ name: 'sda', temp_c: 35, smart: 'ok' }],
  network: { rx_mbps: 1, tx_mbps: 1 },
  backup: { status: 'ok', at: '2026-09-30T03:31:00+02:00' },
  ...over,
})

const svc = (name: string, status: Service['status']): Service => ({
  id: name.toLowerCase(), name, group: 'x', description: '', port: 1, path: '/',
  container: null, widget: null, status,
})

describe('attentionItems', () => {
  it('is empty when all is well', () => {
    expect(attentionItems(nas(), [svc('Sonarr', 'up'), svc('Notes', 'unknown')], NOW)).toEqual([])
  })

  it('flags full pools, disks, backups and services, worst first', () => {
    const items = attentionItems(
      nas({
        storage: {
          used_pct: 60,
          pools: [{ name: 'volume2', used_bytes: 1, total_bytes: 1, used_pct: 98.5, free_bytes: 0 }],
        },
        disks: [
          { name: 'sda', temp_c: 35, smart: 'warn' },
          { name: 'sdb', temp_c: 35, smart: 'fail' },
        ],
        backup: { status: 'fail', at: '2026-09-30T03:31:00+02:00' },
      }),
      [svc('Radarr', 'down'), svc('Immich', 'unhealthy')],
      NOW,
    )

    expect(items).toEqual([
      { level: 'down', text: 'Disk sdb is failing' },
      { level: 'down', text: 'Last backup failed' },
      { level: 'down', text: 'Radarr: stopped' },
      { level: 'warn', text: 'Disk sda has SMART warnings' },
      { level: 'warn', text: 'volume2 98% full' },
      { level: 'warn', text: 'Immich is unhealthy' },
    ])
  })

  it('flags a missed or unknown backup', () => {
    const old = nas({ backup: { status: 'ok', at: '2026-09-28T03:31:00+02:00' } })
    expect(attentionItems(old, [], NOW)).toEqual([{ level: 'warn', text: 'No backup in the last day' }])

    const unknown = nas({ backup: { status: 'unknown', at: null } })
    expect(attentionItems(unknown, [], NOW)).toEqual([{ level: 'warn', text: 'Backup status unknown' }])
  })

  it('flags stale NAS figures', () => {
    expect(attentionItems(nas({ stale: true }), [], NOW)).toEqual([
      { level: 'warn', text: 'NAS figures are out of date' },
    ])
  })

  it('flags a site that is down, but not one without heartbeats yet', () => {
    const site = (name: string, up: boolean | null) => ({
      id: 1, name, group: 'Hubble', up, down_since: null, ping_ms: null, uptime_pct: null, days: [],
    })

    expect(attentionItems(nas(), [], NOW, [site('Meteor Website', false), site('Admin Website', null), site('AOC', true)])).toEqual([
      { level: 'down', text: 'Meteor Website is down' },
    ])
  })
})
