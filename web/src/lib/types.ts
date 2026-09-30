// Shapes of the hub API responses the web app reads. Mirrors collector/app/models.py.

export type ServiceStatus = 'up' | 'starting' | 'unhealthy' | 'down' | 'missing' | 'unknown'

export interface Stat {
  label: string
  value: number
  unit: 'count' | 'bytes' | 'bytes_per_second' | 'percent'
}

export interface Service {
  id: string
  name: string
  group: string
  description: string
  port: number
  path: string
  container: string | null
  widget: string | null
  status: ServiceStatus
  /** Live stats from the service's widget; null without a widget or when it failed. */
  stats?: Stat[] | null
  stats_error?: string | null
}

export interface ServicesResponse {
  as_of: string | null
  stale: boolean
  groups: { name: string; services: Service[] }[]
}

export interface Hosts {
  as_of: string
  stale: boolean
  lan: string
  tailscale: { dns_name: string; ip: string | null } | null
}

/** A catalog entry as edited in Settings (no status or stats). */
export type CatalogService = Omit<Service, 'status' | 'stats' | 'stats_error'>

export interface SettingsCatalog {
  services: CatalogService[]
  widgets: string[]
}

export interface ContainerList {
  as_of: string
  stale: boolean
  containers: { name: string; state: string; health: string | null }[]
}

/** What the service form sends; the collector derives the id for new services. */
export interface ServiceInput {
  name: string
  group: string
  description: string
  port: number
  path: string
  container: string | null
  widget: string | null
}
