// Shapes of the hub API responses the web app reads. Mirrors collector/app/models.py.

export type ServiceStatus = 'up' | 'starting' | 'unhealthy' | 'down' | 'missing' | 'unknown'

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

/** A catalog entry as edited in Settings (no status). */
export type CatalogService = Omit<Service, 'status'>

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
