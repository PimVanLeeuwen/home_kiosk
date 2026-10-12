import { Card, StaleNote } from '../home/Card'
import { cn } from '../../lib/cn'
import { formatWhen } from '../../lib/format'
import type { Exposure, PortScan, PublicHost } from '../../lib/types'
import { useApi } from '../../lib/useApi'
import { GlowDot } from '../ui/GlowDot'

function answer(host: PublicHost): string {
  if (host.status != null) return `answers ${host.status}`
  return host.error ?? 'no answer'
}

/** A shield with a check when nothing unexpected is public, an exclamation mark when something is. */
function Shield({ ok }: { ok: boolean }) {
  const color = ok ? 'var(--color-up)' : 'var(--color-down)'
  return (
    <svg role="img" aria-label={ok ? 'Nothing unexpected is public' : 'Something unexpected is public'} viewBox="0 0 60 60" className="size-16 shrink-0">
      <circle cx="30" cy="30" r="25" fill="none" stroke={color} strokeOpacity="0.45" strokeDasharray="1.5 2.4" />
      <path
        d="M30 11 L45 17 V29 C45 39 38 46 30 49 C22 46 15 39 15 29 V17 Z"
        fill={color}
        fillOpacity="0.13"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
      {ok ? (
        <path d="M23.5 30l4.5 4.5 8.5-9" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M30 22v10M30 37v.5" stroke={color} strokeWidth="2.8" strokeLinecap="round" />
      )}
    </svg>
  )
}

/** The newest port scan from outside: what answered, or why it did not run. */
function ScanLine({ scan }: { scan: PortScan | undefined }) {
  const last = scan?.runs[0]
  if (!last) {
    return (
      <p className="flex items-center gap-2.5">
        <GlowDot tone="muted" />
        <span className="text-muted">No scan received yet. It runs nightly from a GitHub workflow (README, Port scan from outside).</span>
      </p>
    )
  }
  if (last.error) {
    return (
      <p className="flex items-center gap-2.5">
        <GlowDot tone="warn" />
        <span className="text-warn">
          The scan of {formatWhen(last.finished)} failed: {last.error}
        </span>
      </p>
    )
  }
  return (
    <p className="flex items-center gap-2.5">
      <GlowDot tone={last.open.length ? 'down' : 'up'} halo={last.open.length > 0} />
      <span>
        <span className={last.open.length ? 'font-semibold text-down' : 'text-muted'}>
          {last.open.length
            ? `Open on the home IP: ${last.open.join(', ')}.`
            : `No open ports (all ${last.ports_checked.toLocaleString('nl-NL')} checked).`}
        </span>{' '}
        <span className="text-faint">Scanned {formatWhen(last.finished)}.</span>
      </span>
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
  // Without a list there is nothing to conclude.
  const verdict = data.hosts.length > 0 || !data.error

  return (
    <Card
      title="Exposure"
      actions={<span className="text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Every 6 hours</span>}
    >
      <div className="mb-3.5 flex items-center gap-3.5">
        {verdict && <Shield ok={unexpected.length === 0} />}
        <div className="min-w-0">
          {verdict && (
            <p className={cn('text-[17px] leading-snug font-semibold', unexpected.length > 0 && 'text-down')}>
              {unexpected.length
                ? `${unexpected.length} hostname${unexpected.length === 1 ? '' : 's'} not on the allowlist`
                : 'Nothing public beyond the allowlist'}
            </p>
          )}
          <p className="text-[12.5px] text-muted">
            Public names in <span className="font-mono text-[12px]">{data.zone}</span> that lead to the house, from
            Cloudflare&apos;s DNS and tunnel settings, each requested from outside. Checked {formatWhen(data.as_of)}.
          </p>
        </div>
      </div>
      {data.error && (
        <p role="status" className="mb-3 text-[13px] text-warn">
          {data.hosts.length ? 'Showing the last known list. ' : ''}
          {data.error}
        </p>
      )}
      {data.hosts.length > 0 && (
        <ul className="grid gap-2">
          {data.hosts.map((host) => (
            <li
              key={host.hostname}
              className={cn(
                'rounded-[10px] border px-3 py-2.5',
                host.allowed
                  ? 'border-glass-line bg-glass'
                  : 'border-down/40 bg-linear-to-br from-down/12 to-down/[0.03]',
              )}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="font-mono text-[12.5px] break-all">{host.hostname}</span>
                <span className={cn('flex items-center gap-1.5 text-[12.5px] font-semibold', host.allowed ? 'text-up' : 'text-down')}>
                  {!host.allowed && <GlowDot tone="down" halo className="size-[7px]" />}
                  {host.allowed ? 'Allowed' : 'Not allowed'}
                </span>
              </div>
              <p className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[12px] text-muted">
                <span
                  className={cn(
                    'rounded-[6px] px-1.5 text-[10.5px] font-semibold tracking-[0.04em] uppercase',
                    host.source === 'tunnel' ? 'bg-accent/18 text-accent-fg' : 'bg-[#8cc4ff]/14 text-[#8cc4ff]',
                  )}
                >
                  {host.source === 'tunnel' ? 'Tunnel' : 'DNS'}
                </span>
                <span className="font-mono text-[11.5px] break-all">{host.target}</span>
                <span>· {answer(host)}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3.5 border-t border-line-soft pt-3 text-[12.5px]">
        <p className="mb-1.5 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">Port scan from outside</p>
        <ScanLine scan={scan} />
      </div>
      {data.stale && <StaleNote />}
    </Card>
  )
}
