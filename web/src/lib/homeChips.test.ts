import { homeChips } from './homeChips'
import { backupRun, nasFixture } from '../test/fixtures'
import type { BackupHistory, DnsStats } from './types'

describe('homeChips', () => {
  it('shows the last nights in the backup meter, oldest first, padded to 14', () => {
    const backups = { runs: [backupRun(28, false), backupRun(27), backupRun(26)] } as BackupHistory
    const chips = homeChips({ nas: nasFixture(), services: [], backups, outside: undefined, dns: undefined, attention: [], now: new Date() })
    const meter = chips.find((c) => c.id === 'backups')!.meter
    expect(meter).toHaveLength(14)
    expect(meter.slice(-3)).toEqual(['up', 'up', 'down'])
    expect(meter[0]).toBe('off')
  })

  it('shows the share blocked, and the hours without a lookup as gaps in the meter', () => {
    const dns = {
      answering: true, protection: true, share: 12.3,
      hours: [{ queries: 0, blocked: 0 }, { queries: 40, blocked: 3 }],
    } as DnsStats
    const chip = (d: DnsStats | undefined) =>
      homeChips({ nas: undefined, services: undefined, backups: undefined, outside: undefined, dns: d, attention: [], now: new Date() })
        .find((c) => c.id === 'dns')!

    expect(chip(dns)).toMatchObject({ label: 'Ads blocked', value: '12,3%', tone: 'ok', meter: ['off', 'accent'] })
    expect(chip({ ...dns, answering: false })).toMatchObject({ value: 'Down', tone: 'warn' })
    expect(chip({ ...dns, protection: false })).toMatchObject({ value: 'Paused', tone: 'warn' })
    expect(chip(undefined)).toMatchObject({ value: 'Unknown', tone: 'unknown' })
  })
})
