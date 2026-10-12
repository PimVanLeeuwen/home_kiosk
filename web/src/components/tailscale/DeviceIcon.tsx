import { Laptop, Monitor, Server, Smartphone, Tablet, Tv } from 'lucide-react'
import { deviceKind } from '../../lib/tailnet'
import type { TailnetDevice } from '../../lib/types'

/** An icon by kind of device: laptop, phone, tablet, TV, desktop, else a server. */
export function DeviceIcon({ device, className }: { device: Pick<TailnetDevice, 'os' | 'name'>; className?: string }) {
  const props = { 'aria-hidden': true, className, 'data-kind': deviceKind(device) }
  switch (deviceKind(device)) {
    case 'laptop':
      return <Laptop {...props} />
    case 'phone':
      return <Smartphone {...props} />
    case 'tablet':
      return <Tablet {...props} />
    case 'tv':
      return <Tv {...props} />
    case 'desktop':
      return <Monitor {...props} />
    default:
      return <Server {...props} />
  }
}
