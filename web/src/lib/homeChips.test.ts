import { homeChips } from './homeChips'
import { backupRun, nasFixture } from '../test/fixtures'
import type { BackupHistory } from './types'

describe('homeChips', () => {
  it('shows the last nights in the backup meter, oldest first, padded to 14', () => {
    const backups = { runs: [backupRun(28, false), backupRun(27), backupRun(26)] } as BackupHistory
    const chips = homeChips({ nas: nasFixture(), services: [], backups, outside: undefined, attention: [], now: new Date() })
    const meter = chips.find((c) => c.id === 'backups')!.meter
    expect(meter).toHaveLength(14)
    expect(meter.slice(-3)).toEqual(['up', 'up', 'down'])
    expect(meter[0]).toBe('off')
  })
})
