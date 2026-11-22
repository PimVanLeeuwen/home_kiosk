import { AppleCard } from '../components/home/AppleCard'
import { PageHeader } from '../components/PageHeader'
import { Cell, CellGrid } from '../components/ui/CellGrid'
import { GlowDot } from '../components/ui/GlowDot'
import { Loading, Unavailable } from '../components/ui/states'
import { formatAgo } from '../lib/format'
import type { AppleDevice, AppleDevices } from '../lib/types'
import { useApi } from '../lib/useApi'

const KIND: Record<NonNullable<AppleDevice['kind']>, string> = { tv: 'Apple TV', homepod: 'HomePod', homepod_mini: 'HomePod mini' }

/** "Apple TV · Thread border router" and where it stands. */
function DeviceRow({ device, now }: { device: AppleDevice; now: Date }) {
  const kind = [device.kind ? KIND[device.kind] : null, device.thread !== null ? 'Thread border router' : null].filter(Boolean).join(' · ')
  const state = !device.online
    ? `Offline${device.offline_since ? `, went off ${formatAgo(device.offline_since, now)}` : ''}`
    : device.thread === false
      ? 'Online, Thread off'
      : 'Online'
  return (
    <li className="flex items-center gap-3 py-2">
      <GlowDot tone={device.online && device.thread !== false ? 'up' : 'warn'} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{device.name}</span>
        {kind && <span className="block text-small text-muted">{kind}</span>}
      </span>
      <span className={device.online && device.thread !== false ? 'text-small text-muted' : 'text-small text-warn'}>{state}</span>
    </li>
  )
}

/**
 * Home's Apple devices tab (plan.md M38, 5f), built from Today's Apple devices card: the house
 * with its rooms and Thread network, then every device per room with its state.
 */
export function AppleDevicesPage() {
  const { data, error } = useApi<AppleDevices>('/api/apple', 60_000)
  const now = new Date()

  return (
    <>
      <PageHeader title="Apple devices" subtitle="Apple TVs and HomePods per room, the Thread network and what plays" />
      {!data && (error ? <Unavailable what="The Apple devices" /> : <Loading />)}
      {data && data.rooms.length === 0 && <p className="text-muted">No Apple devices found yet.</p>}
      {data && data.rooms.length > 0 && (
        <div className="grid gap-5">
          <AppleCard data={data} onPage />
          <CellGrid label="Rooms" columns={3}>
            {data.rooms.map((room) => (
              <Cell key={room.id} title={room.name}>
                <ul className="-my-2 divide-y divide-line-soft">
                  {room.devices.map((d) => (
                    <DeviceRow key={d.id} device={d} now={now} />
                  ))}
                </ul>
              </Cell>
            ))}
          </CellGrid>
        </div>
      )}
    </>
  )
}
