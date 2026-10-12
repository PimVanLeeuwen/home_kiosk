import type { OutsideService, OutsideServices } from '../lib/types'

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()

const KEYS: [string, string][] = [
  ['github', 'GitHub'],
  ['cloudflare', 'Cloudflare'],
  ['docker', 'Docker Hub'],
  ['tailscale', 'Tailscale'],
  ['hetzner', 'Hetzner'],
  ['transip', 'TransIP'],
  ['proton', 'Proton'],
]

export function outsideService(key: string, over: Partial<OutsideService> = {}): OutsideService {
  const name = KEYS.find(([k]) => k === key)?.[1] ?? key
  return { key, name, url: `https://status.${key}.test`, state: 'ok', incidents: [], as_of: ago(1), stale: false, error: null, ...over }
}

export function outsideServices(over: Record<string, Partial<OutsideService>> = {}, stale = false): OutsideServices {
  return { as_of: ago(1), stale, services: KEYS.map(([k]) => outsideService(k, over[k])) }
}

export const ACTIONS_DELAYED: Partial<OutsideService> = {
  state: 'degraded',
  incidents: [
    {
      title: 'Actions runs are delayed',
      impact: 'degraded',
      status: 'identified',
      started_at: ago(24),
      url: 'https://stspg.io/actions',
      updates: [
        { at: ago(22), status: 'investigating', text: 'We are investigating reports of delayed runs.' },
        { at: ago(9), status: 'identified', text: 'Workflow runs are delayed; a fix is rolling out.' },
      ],
    },
  ],
}
