import { useState, type ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { formatAgo, formatBytes } from '../../lib/format'
import { osName, relayName } from '../../lib/tailnet'
import type { TailnetDevice } from '../../lib/types'
import { GlowDot } from '../ui/GlowDot'
import { DeviceIcon } from './DeviceIcon'

/** Copies a value; only offered where the browser allows it (HTTPS, or the Tailscale address). */
export function CopyButton({ value, what }: { value: string; what: string }) {
  const [copied, setCopied] = useState(false)
  if (!navigator.clipboard) return null
  return (
    <button
      type="button"
      aria-label={`Copy ${what}`}
      onClick={() =>
        navigator.clipboard.writeText(value).then(() => {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1500)
        })
      }
      className="ml-1.5 rounded-[6px] border border-glass-line bg-glass px-1.5 align-[1px] font-sans text-[10.5px] text-muted hover:text-fg"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

/** Label and value pairs; side by side on wide screens, stacked on a phone. */
export function Facts({ rows, className }: { rows: [string, ReactNode][]; className?: string }) {
  return (
    <dl className={cn('grid grid-cols-1 gap-x-4 text-[13px] sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-y-1.5 [&>div:first-child>dt]:mt-0', className)}>
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="mt-2 text-[11.5px] text-faint sm:mt-0 sm:text-[13px]">{label}</dt>
          <dd className="m-0 min-w-0 [overflow-wrap:anywhere]">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

const Mono = ({ children }: { children: ReactNode }) => <span className="font-mono text-[12.5px]">{children}</span>

function Chip({ tone, children }: { tone?: 'direct' | 'relay' | 'exit'; children: ReactNode }) {
  return (
    <span
      className={cn(
        'rounded-[6px] border px-[7px] text-[11px] whitespace-nowrap',
        tone === 'direct' && 'border-up/25 text-up',
        tone === 'relay' && 'border-accent-line/30 text-accent-fg',
        tone === 'exit' && 'border-transparent bg-accent text-white',
        !tone && 'border-glass-line bg-white/5 text-muted',
      )}
    >
      {children}
    </span>
  )
}

interface Props {
  device: TailnetDevice
  open: boolean
  onToggle: () => void
  now: Date
}

/** A device as a glass tile; tap it for the addresses and how it connects. */
export function DeviceTile({ device: d, open, onToggle, now }: Props) {
  const how = d.connection === 'relay' && d.relay ? `relay ${d.relay}` : d.connection
  return (
    <li
      className={cn(
        'rounded-[12px] border',
        open ? 'col-span-full border-accent-line/35 bg-accent/10' : 'border-glass-line bg-glass',
        !d.online && !open && 'opacity-75',
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="grid w-full grid-cols-[40px_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-3.5 py-3 text-left"
      >
        <span
          className={cn(
            'grid size-10 place-items-center rounded-[11px] border bg-raised',
            d.online ? 'border-up/40 shadow-[0_0_14px_-5px_var(--color-up)]' : 'border-dashed border-white/18 text-faint',
          )}
        >
          <DeviceIcon device={d} className="size-[18px]" />
        </span>
        <span className="min-w-0">
          <span className="flex items-center gap-2 text-[14px] font-medium">
            {d.name}
            {d.online && <GlowDot tone="up" label="Online" className="size-1.5" />}
          </span>
          <span className="block truncate font-mono text-[11.5px] text-faint">{d.dns_name}</span>
        </span>
        <span className="font-mono text-[13px]">{d.ipv4}</span>
        <span className="col-start-2 col-end-4 mt-1 flex flex-wrap gap-1.5">
          {d.os && <Chip>{osName(d.os)}</Chip>}
          {d.online ? (
            how && <Chip tone={d.connection === 'idle' ? undefined : (d.connection ?? undefined)}>{how}</Chip>
          ) : (
            <Chip>{d.last_seen ? `last seen ${formatAgo(d.last_seen, now)}` : 'offline'}</Chip>
          )}
          {d.exit_node && <Chip tone="exit">Exit node</Chip>}
        </span>
      </button>

      {open && (
        <div className="mx-3.5 mb-3.5 ml-[66px] border-t border-glass-line pt-3">
          <Facts
            className="lg:grid-cols-[auto_minmax(0,1fr)_auto_minmax(0,1fr)]"
            rows={detailRows(d, now)}
          />
        </div>
      )}
    </li>
  )
}

function detailRows(d: TailnetDevice, now: Date): [string, ReactNode][] {
  const rows: ([string, ReactNode] | false)[] = [
    !!d.ipv4 && ['IPv4', <><Mono>{d.ipv4}</Mono><CopyButton value={d.ipv4} what="IPv4 address" /></>],
    !!d.ipv6 && ['IPv6', <><Mono>{d.ipv6}</Mono><CopyButton value={d.ipv6} what="IPv6 address" /></>],
    ['MagicDNS', <><Mono>{d.dns_name}</Mono><CopyButton value={d.dns_name} what="MagicDNS name" /></>],
    d.online && ['Connection', connectionText(d)],
    d.online && ['Traffic', <>{formatBytes(d.rx_bytes)} in · {formatBytes(d.tx_bytes)} out <span className="text-faint">since tailscaled started</span></>],
    !d.online && ['Last seen', d.last_seen ? formatAgo(d.last_seen, now) : 'never'],
  ]
  return rows.filter((row): row is [string, ReactNode] => !!row)
}

function connectionText(d: TailnetDevice): ReactNode {
  if (d.connection === 'direct') return d.endpoint ? <>direct to <Mono>{d.endpoint}</Mono></> : 'direct'
  if (d.connection === 'relay') return d.relay ? `through the relay in ${relayName(d.relay)}` : 'through a relay'
  return 'idle: no traffic lately, so no path yet'
}
