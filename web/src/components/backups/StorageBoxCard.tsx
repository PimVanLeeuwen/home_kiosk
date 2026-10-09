import { Card } from '../home/Card'
import { Meter } from '../home/Meter'
import { formatBytes, formatRunway, formatWhen } from '../../lib/format'
import type { StorageBox } from '../../lib/types'

// The default of the "Storage box space" alert rule.
const BOX_FULL_PCT = 85

/** Space on the Hetzner storage box, measured by the nightly backup. */
export function StorageBoxCard({ box }: { box: StorageBox }) {
  return (
    <Card title="Storage box" className="mb-5">
      <Meter
        label="Hetzner"
        value={`${formatBytes(box.used)} / ${formatBytes(box.total)}`}
        pct={box.used_pct}
        tone={box.used_pct >= 97 ? 'down' : box.used_pct >= BOX_FULL_PCT ? 'warn' : 'ok'}
      />
      <p className="mt-1 flex flex-wrap justify-between gap-x-3 text-[12px] text-faint">
        <span>
          {box.used_pct.toFixed(1).replace('.', ',')}% used · {formatBytes(box.free)} free
        </span>
        <span>{formatRunway(box.projection_months)}</span>
      </p>
      <p className="mt-2 text-[12.5px] text-muted">Measured after the backup of {formatWhen(box.at)}.</p>
    </Card>
  )
}
