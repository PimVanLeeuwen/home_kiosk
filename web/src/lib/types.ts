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
