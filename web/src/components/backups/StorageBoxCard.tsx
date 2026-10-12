import { formatBytes, formatRunway, formatWhen } from '../../lib/format'
import { shortRunway } from '../../lib/nasHealth'
import type { StorageBox } from '../../lib/types'
import { Card } from '../home/Card'
import { ArcGauge } from '../ui/ArcGauge'
import { Pill } from '../ui/Pill'

// The default of the "Storage box space" alert rule.
const BOX_FULL_PCT = 85

/** Space on the Hetzner storage box, measured by the nightly backup, on a dial with the alert mark. */
export function StorageBoxCard({ box }: { box: StorageBox }) {
  const full = box.used_pct >= BOX_FULL_PCT
  return (
    <Card title="Storage box" actions={<Pill tone={full ? 'warn' : 'up'}>{full ? 'Nearly full' : 'Room left'}</Pill>}>
      <ArcGauge pct={box.used_pct} alertAt={BOX_FULL_PCT} label="Hetzner" />
      <div className="mt-1 text-center text-[12.5px]">
        <p className="text-muted">
          {formatBytes(box.used)} of {formatBytes(box.total)} · {formatBytes(box.free)} free
        </p>
        <p className={shortRunway(box) ? 'text-warn' : 'text-faint'}>{formatRunway(box.projection_months)}</p>
        <p className="mt-1.5 text-faint">Measured after the backup of {formatWhen(box.at)}</p>
      </div>
    </Card>
  )
}
