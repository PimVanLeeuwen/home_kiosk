import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { Exposure, PortScan, PublicHost } from '../../lib/types'
import { useApi } from '../../lib/useApi'

function answer(host: PublicHost): string {
  if (host.status != null) return `answers ${host.status}`
  return host.error ?? 'no answer'
}

/** The newest port scan from outside: what answered, or why it did not run. */
function ScanLine({ scan }: { scan: PortScan | undefined }) {
  const last = scan?.runs[0]
  if (!last) {
    return (
      <p className="text-muted">No scan received yet. It runs nightly from a GitHub workflow (README, Port scan from outside).</p>
    )
  }
  if (last.error) {
    return (
      <p className="text-warn">
        The scan of {formatWhen(last.finished)} failed: {last.error}
      </p>
    )
  }
  return (
    <p className={last.open.length ? 'text-down' : 'text-muted'}>
      {last.open.length
        ? `Open on the home IP: ${last.open.join(', ')}.`
        : `No open ports (all ${last.ports_checked.toLocaleString('nl-NL')} checked).`}{' '}
      <span className="text-muted">Scanned {formatWhen(last.finished)}.</span>
    </p>
  )
}

/** Every public hostname that leads to the house, from Cloudflare, and the port scan from
 * outside. Hidden when the audit is off. */
export function ExposureCard() {
  const { data } = useApi<Exposure>('/api/exposure', 300_000)
  const { data: scan } = useApi<PortScan>('/api/exposure/scan', 300_000)
  if (!data) return null
  const unexpected = data.hosts.filter((h) => !h.allowed)

  return (
    <Card title="Exposure">
      <p className="mb-3 text-[13px] text-muted">
        Public hostnames in <span className="font-mono text-[12px]">{data.zone}</span> that lead to the house, from
        Cloudflare&apos;s DNS and tunnel settings, each requested from outside. Checked every 6 hours.
      </p>
      {data.error && (
        <p role="status" className="mb-3 text-[13px] text-warn">
          {data.hosts.length ? 'Showing the last known list. ' : ''}
          {data.error}
        </p>
      )}
      {data.hosts.length > 0 && (
        <ul className="divide-y divide-line-soft text-[13.5px]">
          {data.hosts.map((host) => (
            <li key={host.hostname} className="py-2 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="font-mono text-[12.5px] break-all">{host.hostname}</span>
                <span className={cn('font-semibold', host.allowed ? 'text-up' : 'text-down')}>
                  {host.allowed ? 'Allowed' : 'Not allowed'}
                </span>
              </div>
              <p className="text-[12.5px] text-muted">
                {host.source === 'tunnel' ? 'Tunnel to' : 'DNS'}{' '}
                <span className="font-mono text-[12px]">{host.target}</span> · {answer(host)}
              </p>
            </li>
          ))}
        </ul>
      )}
      {/* Without a list there is nothing to conclude. */}
      {(data.hosts.length > 0 || !data.error) && (
        <p className={cn('mt-3 text-[12.5px]', unexpected.length ? 'text-down' : 'text-muted')}>
          {unexpected.length
            ? `${unexpected.length} hostname${unexpected.length === 1 ? '' : 's'} not on the allowlist.`
            : 'Nothing public beyond the allowlist.'}{' '}
          <span className="text-muted">Checked {formatWhen(data.as_of)}.</span>
        </p>
      )}
      <div className="mt-4 border-t border-line-soft pt-3 text-[12.5px]">
        <p className="mb-1 text-faint">Port scan from outside</p>
        <ScanLine scan={scan} />
      </div>
      {data.stale && <StaleNote />}
    </Card>
  )
}
