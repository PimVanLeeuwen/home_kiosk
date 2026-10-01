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
  /** A NAS service has a port and path; an external link has a url instead. */
  port: number | null
  path: string
  url?: string | null
  container: string | null
  widget: string | null
  /** Name of a bundled icon (lib/icons.ts); letters when unset. */
  icon?: string | null
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
  tailscale: {
    dns_name: string
    ip: string | null
    /** tailscale serve HTTPS port by local port, e.g. { "8096": 18096 }. */
    https_ports?: Record<string, number>
  } | null
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
  port: number | null
  path: string
  url: string | null
  container: string | null
  widget: string | null
  icon: string | null
}

// Kiosk payloads, reused by the Home page. Mirrors collector/app/models.py.

export interface Portfolio {
  as_of: string
  stale: boolean
  currency: string
  total_value: number
  change: { day_abs: number; day_pct: number; month_pct: number; year_pct: number; all_pct: number }
  history: { d: string; v: number }[]
  holdings: { symbol: string; name: string; value: number; day_pct: number; weight_pct: number }[]
}

export interface Pool {
  name: string
  used_bytes: number
  total_bytes: number
  used_pct: number
  free_bytes: number
  projection_months?: number | null
}

export interface Nas {
  as_of: string
  stale: boolean
  host: string
  storage: { used_pct: number; pools: Pool[] }
  cpu_pct: number
  ram_pct: number
  cpu_temp_c: number | null
  containers: { running: number; total: number }
  disks: { name: string; temp_c: number | null; smart: 'ok' | 'warn' | 'fail' }[]
  /** Megabits per second. */
  network: { rx_mbps: number; tx_mbps: number }
  backup: { status: 'ok' | 'fail' | 'unknown'; at: string | null }
}

export interface NewsItem {
  title: string
  source: string
  published: string
  age_label: string
  url: string
}

export interface NewsResponse {
  as_of: string
  stale: boolean
  groups: { id: string; title: string; items: NewsItem[] }[]
}

export interface Repo {
  name: string
  full_name: string
  url: string
  description: string | null
  private: boolean
  fork: boolean
  language: string | null
  language_color: string | null
  stars: number
  forks: number
  pushed_at: string | null
  open_prs: number
  open_issues: number
  ci: 'passing' | 'failing' | 'running' | 'none'
  release: { tag: string; published_at: string | null; url: string } | null
}

export interface ReposResponse {
  as_of: string
  stale: boolean
  groups: { login: string; label: string; repos: Repo[]; error: string | null }[]
}

export interface ContainerLoad {
  name: string
  project: string | null
  image: string
  state: string
  health: 'healthy' | 'unhealthy' | 'starting' | null
  status: string
  /** Share of the whole NAS, in percent; null before two readings or when stopped. */
  cpu_pct: number | null
  mem_bytes: number | null
  mem_limit: number | null
  rx_bps: number | null
  tx_bps: number | null
}

export interface DockerOverview {
  as_of: string
  stale: boolean
  containers: ContainerLoad[]
  cpu_pct: number
  mem_bytes: number
}

export interface ContainerPoint {
  t: string
  cpu: number | null
  mem: number | null
}

export interface ContainerUpdate {
  at: string
  name: string
  image: string
  old_image_id: string
  new_image_id: string
}

/** CPU per container in 30-minute averages, oldest first. */
export type Sparklines = Record<string, (number | null)[]>
