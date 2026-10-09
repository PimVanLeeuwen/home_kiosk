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
  uptime_seconds?: number
  mem_total_bytes?: number | null
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
  /** One per configured token, by the owner labels it reads. */
  tokens?: GitHubToken[]
}

export interface GitHubToken {
  owners: string[]
  /** null: no expiry date, or not known yet. */
  expires_at: string | null
  /** GitHub has answered a request with it. */
  checked: boolean
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

/** One 10-minute average on the NAS page charts. Network in megabits per second. */
export interface NasPoint {
  t: string
  cpu: number | null
  ram: number | null
  temp: number | null
  rx_mbps: number | null
  tx_mbps: number | null
}

export interface BackupVolume {
  name: string
  ok: boolean
  exit_code: number
  seconds: number
  /** rclone's final stats; null when a run left none. */
  bytes: number | null
  transfers: number | null
  checks: number | null
  deletes: number | null
  errors: number | null
  last_error: string | null
}

export interface BackupRun {
  started: string
  finished: string
  ok: boolean
  volumes: BackupVolume[]
}

export interface BackupHistory {
  as_of: string
  stale: boolean
  /** Newest first. */
  runs: BackupRun[]
  volumes: { name: string; last_run: BackupRun | null; last_success: string | null }[]
  next_due: string | null
  /** Space on the Hetzner storage box at the newest run that measured it. */
  storage_box?: StorageBox | null
}

export interface StorageBox {
  total: number
  used: number
  free: number
  used_pct: number
  /** The run that measured it. */
  at: string
  projection_months: number | null
}

export interface MirroredRepo {
  full_name: string
  archived: boolean
  /** This run's result; `mirrored_at` is the last time it succeeded. */
  ok: boolean
  error: string | null
  mirrored_at: string | null
  bytes: number | null
}

export interface MirrorRun {
  started: string
  finished: string
  ok: boolean
  repos: number
  failed: number
  removed: number
  bytes: number
}

/** The nightly git mirror of the GitHub repos (GET /api/github-mirror). */
export interface GitHubMirror {
  as_of: string
  stale: boolean
  enabled: boolean
  dir: string
  /** The whole run could not start, such as a missing mount. */
  error: string | null
  owners: { login: string; label: string; repos: MirroredRepo[]; removed: string[]; error: string | null }[]
  /** Newest first. */
  runs: MirrorRun[]
  last_success: string | null
  next_due: string | null
}

export interface PublicHost {
  hostname: string
  /** A tunnel route, or a DNS record on the house. */
  source: 'tunnel' | 'dns'
  target: string
  allowed: boolean
  /** The HTTPS answer from outside; null when there was none. */
  status: number | null
  error: string | null
}

/** The exposure audit (GET /api/exposure). */
export interface Exposure {
  as_of: string
  stale: boolean
  zone: string
  home_ip: string | null
  hosts: PublicHost[]
  /** The audit could not run; hosts are then the last known list. */
  error: string | null
}

/** The nightly port scan of the home IP from outside (GET /api/exposure/scan). */
export interface PortScan {
  as_of: string
  stale: boolean
  /** Newest first. */
  runs: { started: string; finished: string; ports_checked: number; open: number[]; error: string | null }[]
}

export interface UpsOutage {
  started_at: string
  /** null while it lasts. */
  ended_at: string | null
  lowest_charge: number | null
  /** The charge reached the level where UGOS stops all services. */
  reached_low: boolean
}

/** The UPS over NUT (GET /api/ups). */
export interface Ups {
  as_of: string
  stale: boolean
  name: string
  model: string | null
  status: 'online' | 'on_battery' | 'low_battery' | 'unknown'
  status_raw: string
  charge: number | null
  charge_low: number | null
  load: number | null
  /** Newest first; the first is open while it lasts. */
  outages: UpsOutage[]
}

export interface DumpedDatabase {
  name: string
  label: string
  kind: 'pg_dump' | 'sqlite'
  /** The newest attempt; null when there is none yet. */
  ok: boolean | null
  at: string | null
  bytes: number | null
  error: string | null
  last_success: string | null
}

/** Nightly database dumps: the NAS host job and the hub's own copy (GET /api/database-dumps). */
export interface DatabaseDumps {
  as_of: string
  stale: boolean
  databases: DumpedDatabase[]
  /** The host job's runs, newest first. */
  runs: { started: string; finished: string; ok: boolean; failed: number }[]
  /** The monthly restore check, newest first. */
  restore_checks?: RestoreCheck[]
  /** The newest restore check that passed. */
  last_verified?: string | null
}

export interface RestoreCheck {
  started: string
  finished: string
  ok: boolean
  checks: { name: string; ok: boolean; detail: string }[]
}

export type Severity = 'info' | 'ok' | 'warning' | 'error'

export interface AlertMessage {
  id: number
  ts: string
  source: string
  category: string
  severity: Severity
  title: string
  body: string
  chat: string
  status: 'sent' | 'held' | 'digested' | 'failed'
  error: string | null
  sent_at: string | null
}

/** An editable message wording (Settings → Messages, /api/alerts/templates). */
export interface MessageTemplate {
  id: string
  group: string
  label: string
  description: string
  /** Line templates: the message they are part of. */
  parent: string | null
  /** The category it is routed by, e.g. "Backups"; null for line templates. */
  category: string | null
  placeholders: { name: string; description: string; block: boolean }[]
  default: string
  text: string
  customised: boolean
  /** Telegram HTML with sample values. */
  preview: string
}

export interface QuietHours {
  enabled: boolean
  start: string
  end: string
}

export interface AlertSettings {
  routing: Record<string, string>
  quiet: QuietHours
  categories: Record<string, string>
  chats: { key: string; label: string; configured: boolean }[]
  token_set: boolean
  notify_key_set: boolean
}

export interface RuleSettings {
  enabled: boolean
  threshold_pct?: number
  unhealthy_minutes?: number
  restarts?: number
  restart_window_minutes?: number
  hours?: number
  restore_days?: number
  days?: number
}

export interface AlertRules {
  rules: Record<string, RuleSettings>
  labels: Record<string, string>
}

export interface Incident {
  key: string
  rule: string
  severity: Severity
  title: string
  body: string
  opened_at: string
  last_seen_at: string
  resolved_at: string | null
}
