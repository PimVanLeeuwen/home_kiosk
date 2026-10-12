import { useState, type ReactNode } from 'react'
import { Loading, Unavailable } from '../components/home/Card'
import { PageHeader } from '../components/PageHeader'
import { CopyButton, DeviceTile, Facts } from '../components/tailscale/DeviceTile'
import { TailnetMap } from '../components/tailscale/TailnetMap'
import { GlowDot } from '../components/ui/GlowDot'
import { Pill } from '../components/ui/Pill'
import { relayName } from '../lib/tailnet'
import type { Hosts, Tailnet, TailnetDevice } from '../lib/types'
import { useApi } from '../lib/useApi'

const REFRESH_MS = 60_000

const mono = (value: string) => <span className="font-mono text-[12.5px]">{value}</span>

/** The NAS's own names and addresses, with what is known; empty rows left out. */
function selfRows(self: TailnetDevice, served: number, issues: number): [string, ReactNode][] {
  const rows: ([string, ReactNode] | false)[] = [
    ['MagicDNS', <>{mono(self.dns_name)}<CopyButton value={self.dns_name} what="MagicDNS name" /></>],
    !!self.ipv4 && ['IPv4', <>{mono(self.ipv4)}<CopyButton value={self.ipv4} what="IPv4 address" /></>],
    !!self.ipv6 && ['IPv6', mono(self.ipv6)],
    !!self.relay && ['Home relay', relayName(self.relay)],
    served > 0 && ['Serves', `${served} hub ${served === 1 ? 'service' : 'services'} over HTTPS`],
    ['Health', issues ? <span className="text-warn">{issues} {issues === 1 ? 'issue' : 'issues'}</span> : <span className="text-up">All checks pass</span>],
  ]
  return rows.filter((row): row is [string, ReactNode] => !!row)
}

function Group({ title, devices, open, setOpen, now }: {
  title: string
  devices: TailnetDevice[]
  open: string | null
  setOpen: (name: string | null) => void
  now: Date
}) {
  if (!devices.length) return null
  const id = `devices-${title.toLowerCase()}`
  return (
    <section aria-labelledby={id} className="mt-5">
      <h2 id={id} className="mb-2.5 flex items-center gap-2 text-[11px] font-semibold tracking-[0.08em] text-faint uppercase">
        {title}
        <span className={title === 'Online' ? 'rounded-[6px] bg-up/13 px-1.5 text-up' : 'rounded-[6px] bg-raised px-1.5 text-muted'}>
          {devices.length}
        </span>
      </h2>
      <ul className="grid grid-cols-1 items-start gap-2.5 lg:grid-cols-2">
        {devices.map((d) => (
          <DeviceTile
            key={d.dns_name}
            device={d}
            now={now}
            open={open === d.dns_name}
            onToggle={() => setOpen(open === d.dns_name ? null : d.dns_name)}
          />
        ))}
      </ul>
    </section>
  )
}

export function TailscalePage() {
  const { data, error } = useApi<Tailnet>('/api/tailnet', REFRESH_MS)
  const { data: hosts } = useApi<Hosts>('/api/hosts', 600_000)
  const [open, setOpen] = useState<string | null>(null)
  const now = new Date()

  const online = data ? data.peers.filter((p) => p.online).length + 1 : 0
  const total = data ? data.peers.length + 1 : 0
  const issues = data?.health.length ?? 0
  const stale = !!data && (data.stale || !!error)
  const served = Object.keys(hosts?.tailscale?.https_ports ?? {}).length

  return (
    <>
      <PageHeader
        title="Tailscale"
        subtitle={data ? `${data.name} · ${online} of ${total} online` : 'The tailnet and every device on it'}
        actions={
          data &&
          (stale ? (
            <Pill tone="muted">Stale</Pill>
          ) : issues ? (
            <Pill tone="warn">
              {issues} health {issues === 1 ? 'issue' : 'issues'}
            </Pill>
          ) : (
            <Pill tone="up">Healthy</Pill>
          ))
        }
      />

      {!data && (error ? <Unavailable what="Tailscale" /> : <Loading />)}

      {data && (
        <>
          {stale && (
            <p role="status" className="-mt-3 mb-4 text-[12.5px] text-warn">
              Tailscale could not be read just now; this is the last known state.
            </p>
          )}

          {data.health.map((warning) => (
            <section
              key={warning}
              role="alert"
              className="mb-4 flex items-start gap-3.5 rounded-[14px] border border-warn/35 bg-linear-to-br from-warn/12 to-warn/3 px-5 py-4"
            >
              <span
                aria-hidden="true"
                className="grid size-[30px] shrink-0 place-items-center rounded-full border border-warn/45 bg-warn/14 font-bold text-warn shadow-[0_0_14px_-3px_var(--color-warn)]"
              >
                !
              </span>
              <div>
                <p className="font-semibold text-warn">Tailscale health</p>
                <p className="mt-0.5 text-[13px] text-muted">{warning}</p>
              </div>
            </section>
          ))}

          <section
            aria-label="Tailnet"
            className="grid items-center gap-6 rounded-[14px] border border-line-soft bg-card bg-linear-to-b from-white/[0.022] to-transparent to-40% px-5 py-8 md:px-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]"
          >
            <TailnetMap peers={data.peers} warn={issues > 0} />
            <div>
              <p className="mb-3 flex items-center gap-2.5 text-[19px] font-semibold">
                <GlowDot tone={issues ? 'warn' : 'accent'} halo={issues > 0} />
                {data.self.name}
                <span className="text-[13px] font-normal text-faint">this NAS</span>
              </p>
              <Facts rows={selfRows(data.self, served, issues)} />
            </div>
          </section>

          {data.peers.length === 0 && <p className="mt-5 text-muted">No other devices on the tailnet yet.</p>}
          <Group title="Online" devices={data.peers.filter((p) => p.online)} open={open} setOpen={setOpen} now={now} />
          <Group title="Offline" devices={data.peers.filter((p) => !p.online)} open={open} setOpen={setOpen} now={now} />
        </>
      )}
    </>
  )
}
