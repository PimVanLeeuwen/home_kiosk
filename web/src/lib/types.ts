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

export type MachineState = 'idle' | 'running' | 'paused' | 'done' | 'error'

export interface Machine {
  /** A short hash of ConnectLife's device id. */
  id: string
  /** As named in the ConnectLife app. */
  name: string
  kind: 'washer' | 'dryer'
  state: MachineState
  online: boolean
  program: string | null
  remaining_minutes: number | null
  total_minutes: number | null
  ready_at: string | null
  done_at: string | null
  door_open: boolean
  /** "F05", or a reason ConnectLife names. */
  error: string | null
}

export interface Light {
  id: string
  name: string
  on: boolean
  brightness: number
  kelvin: number | null
  reachable: boolean
}

export interface LightGroup {
  id: string
  name: string
  /** ambiance: whites from warm to cool; white: brightness only. */
  kind: 'ambiance' | 'white'
  on: boolean
  brightness: number
  kelvin: number | null
  lights: Light[]
}

/** The living room's lights through the Hue Bridge (`/api/lights`). */
export interface Lights {
  as_of: string
  stale: boolean
  room: string
  groups: LightGroup[]
  kelvins: number[]
}

export interface AppleDevice {
  id: string
  name: string
  kind: 'tv' | 'homepod' | 'homepod_mini' | null
  online: boolean
  offline_since: string | null
  /** null: not a Thread border router; else whether its Thread interface is active. */
  thread: boolean | null
}

export interface ApplePlaying {
  state: 'playing' | 'paused'
  media: 'video' | 'music' | 'other'
  title: string
  subtitle: string | null
  app: string | null
  /** The id of the device that reported it. */
  device: string
  artwork: boolean
}

/** The Apple TVs and HomePods per room (`/api/apple`). */
export interface AppleDevices {
  as_of: string
  stale: boolean
  rooms: { id: string; name: string; devices: AppleDevice[]; playing: ApplePlaying | null }[]
}

/** The morning digest (`/api/briefing`), written by Claude on weekdays at 06:30. */
export interface Briefing {
  as_of: string
  stale: boolean
  /** The local date it is for, YYYY-MM-DD. */
  date: string
  /** 09:00 that day: Home and the Now panel show it until then. */
  until: string
  line: string
  facts: string[]
  paragraph: string
}

/** Settings, AI (`/api/ai`): this month's spend against the cap and the feature switches. */
export interface AiStatus {
  as_of: string
  stale: boolean
  /** The NAS's .env has an Anthropic API key. */
  configured: boolean
  /** The monthly cap, and what is spent so far (counted in dollars). */
  cap: number
  spent: number
  calls: number
  capped: boolean
  features: { id: string; label: string; on: boolean }[]
}

/** Paperless's full-text search for the command palette (`/api/documents/search`). */
export interface DocumentSearch {
  as_of: string
  stale: boolean
  /** False when Paperless is not set up or did not answer; `reason` says which ("Not reachable"). */
  available: boolean
  reason: string | null
  results: { id: number; title: string; correspondent: string | null; created: string | null }[]
}

/** AdGuard Home's last 24 hours (`/api/dns`): counts only, never per device. */
export interface DnsStats {
  as_of: string
  stale: boolean
  /** False once AdGuard has not answered for a few minutes: the house then resolves through Quad9, unfiltered. */
  answering: boolean
  /** Which part does not answer: DNS lookups, or (without the DNS check) the admin page. */
  failing: 'dns' | 'admin' | null
  failing_since: string | null
  /** Blocking is on (AdGuard can pause it). */
  protection: boolean
  queries: number
  blocked: number
  /** Percent blocked; null before any query. */
  share: number | null
  /** Oldest first; the last one is the current hour. */
  hours: { queries: number; blocked: number }[]
  top_blocked: string | null
  top_blocked_count: number | null
}

/** The living room's air from the ALPSTUGA through the Matter server (`/api/air`). */
export interface Air {
  as_of: string
  stale: boolean
  room: string
  /** The Matter server can reach the sensor. */
  available: boolean
  /** °C, one decimal. */
  temperature: number | null
  /** %. */
  humidity: number | null
  /** ppm. */
  co2: number | null
  /** µg/m³. */
  pm25: number | null
  /** The sensor's own verdict: "Good" to "Extremely poor". */
  quality: string | null
  /** By CO2: below 800, to 1200, above. */
  level: 'fresh' | 'stuffy' | 'open_window' | null
  /** °C, from Buienradar. */
  outside: number | null
  /** CO2 every 5 minutes, the last 8 hours. */
  history: { at: string; co2: number }[]
}

/** The washer and dryer (`/api/laundry`). */
export interface Laundry {
  as_of: string
  stale: boolean
  /** Washers first. */
  machines: Machine[]
  /** A machine runs, is paused, has an error or is done. */
  showing: boolean
}

export interface CalendarEvent {
  calendar_id: string
  calendar: string
  /** "#ff8d28", the calendar's own colour. */
  color: string
  title: string
  /** null for an all-day event. */
  start: string | null
  end: string | null
  all_day: boolean
}

/** Today's events (`/api/calendar`). */
export interface Today {
  as_of: string
  stale: boolean
  /** The local date, YYYY-MM-DD. */
  date: string
  /** Timed events, by start. */
  events: CalendarEvent[]
  all_day: CalendarEvent[]
  /** Calendar name to a short reason, when one could not be read. */
  errors: Record<string, string>
}

/** A calendar in Settings (`/api/settings/calendars`). */
export interface CalendarInfo {
  id: string
  name: string
  color: string
  kind: 'icloud' | 'subscribed'
  shown: boolean
}

export type DeskPanel = 'now' | 'home' | 'house' | 'test'

/** A desk panel board that has asked the hub (Settings → Desk panels). */
export interface DeskBoard {
  mac: string
  panel: DeskPanel | null
  first_seen: string
  last_seen: string
  firmware: string
  update_requested: boolean
  /** Its device key: none, on its way (handed over until the board sends it back), or in use. */
  key: 'none' | 'pending' | 'active'
}

/** The firmware the hub offers the boards (/panels/firmware.json, built by CI). */
export interface PanelFirmware {
  version: string
  size: number
}

export interface Viewer {
  /** Tracearr's username. */
  name: string
  plays: number
  watch_seconds: number
}

export interface MediaLibrary {
  movies: number
  shows: number
  episodes: number
  size_bytes: number
  /** In the last 7 days. */
  added_movies: number
  added_episodes: number
}

export type RequestState = 'waiting' | 'approved' | 'downloading' | 'partly' | 'available' | 'declined' | 'failed'

export interface MediaRequest {
  title: string
  year: string | null
  kind: 'tv' | 'movie'
  /** Seerr's display name of who asked. */
  by: string
  state: RequestState
  poster: string | null
}

/** Watch stats, the library and requests (`/api/media/overview`). */
export interface MediaOverview {
  as_of: string
  stale: boolean
  /** With plays in the last 30 days, most watch time first; null when Tracearr could not be read. */
  viewers: Viewer[] | null
  idle_viewers: number
  /** The household's most-watched, all time. */
  genres: string[]
  library: MediaLibrary | null
  requests: { pending: number; processing: number; available: number; completed: number } | null
  latest_requests: MediaRequest[]
  errors: Record<string, string>
}

export type SiteDay = 'up' | 'blip' | 'down' | 'none'

export interface Site {
  id: number
  /** Kuma's name for the monitor. */
  name: string
  /** Kuma's group on the status page, e.g. "Personal". */
  group: string
  /** null: no heartbeat yet. */
  up: boolean | null
  down_since: string | null
  ping_ms: number | null
  /** Over the recorded part of the last 30 days. */
  uptime_pct: number | null
  /** 30 of them, oldest first, today last. */
  days: SiteDay[]
}

/** The owner's websites from Uptime Kuma (`/api/sites`). */
export interface Sites {
  as_of: string
  stale: boolean
  sites: Site[]
}

export type MediaState = 'downloading' | 'queued' | 'paused' | 'importing' | 'warning' | 'failed'

export interface MediaDownload {
  /** "sonarr:123", the queue item. */
  id: string
  kind: 'tv' | 'movie'
  title: string
  /** "S2 E5 · The Breakwater" or "Movie · 2025". */
  detail: string
  size_bytes: number
  left_bytes: number
  progress_pct: number
  time_left_seconds: number | null
  client: string
  state: MediaState
  /** Sonarr's or Radarr's own reason for a warning or failure. */
  message: string | null
  /** "sonarr/12": served at /api/media/posters/sonarr/12. */
  poster: string | null
}

export interface MediaEpisode {
  series: string
  season: number
  episode: number
  title: string
  air_date: string | null
  poster: string | null
}

/** Downloads, missing episodes and the week ahead (`/api/media`). */
export interface Media {
  as_of: string
  stale: boolean
  downloads: MediaDownload[]
  /** Newest first, at most 10. */
  missing: MediaEpisode[]
  missing_total: number
  /** The coming week, soonest first. */
  upcoming: MediaEpisode[]
  /** Source to a short reason, when Sonarr or Radarr could not be read. */
  errors: Record<string, string>
}

export interface TrainStop {
  name: string
  planned: string
  actual: string | null
  /** The actual platform, else the planned one. */
  track: string | null
  cancelled: boolean
}

export interface TrainRun {
  /** "IC 3522". */
  name: string
  /** late: one minute or more behind; not_found: NS's planner no longer lists it. */
  status: 'on_time' | 'late' | 'cancelled' | 'not_found'
  planned_departure: string
  actual_departure: string | null
  delay_minutes: number
  planned_track: string | null
  actual_track: string | null
  stops: TrainStop[]
}

export interface TrainDisruption {
  id: string
  kind: string
  /** NS's own words, e.g. "Utrecht - Amsterdam." */
  title: string
  text: string
  until: string | null
}

/** The weekday morning train (`/api/train`). */
export interface Train {
  as_of: string
  stale: boolean
  /** The local date of the train, YYYY-MM-DD. */
  date: string
  route: string
  /** "07:16", even when NS no longer lists the train. */
  departure: string
  /** morning: that day's train until it leaves; evening: tomorrow's, the evening before. */
  mode: 'morning' | 'evening' | 'idle'
  /** Show the card: in the morning until it leaves, in the evening only with a problem. */
  watching: boolean
  departed: boolean
  train: TrainRun | null
  next_direct: TrainRun | null
  disruptions: TrainDisruption[]
}

/** One device on the tailnet, from tailscaled's status (`/api/tailnet`). */
export interface TailnetDevice {
  name: string
  dns_name: string
  os: string
  ipv4: string | null
  ipv6: string | null
  online: boolean
  /** Offline devices only. */
  last_seen: string | null
  /** Idle: online, but no recent traffic, so no path yet. Null for the NAS itself. */
  connection: 'direct' | 'relay' | 'idle' | null
  /** DERP region code ("ams"): the relay in use, or the NAS's home relay. */
  relay: string | null
  /** ip:port of a direct path. */
  endpoint: string | null
  exit_node: boolean
  rx_bytes: number
  tx_bytes: number
}

export interface Tailnet {
  as_of: string
  stale: boolean
  /** The MagicDNS suffix's first label, e.g. "tail1234". */
  name: string
  self: TailnetDevice
  /** Online first, then by name. */
  peers: TailnetDevice[]
  /** tailscaled's own health warnings; empty when all checks pass. */
  health: string[]
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
  /** The default branch and its latest commit (older answers lack them). */
  branch?: string | null
  commit_message?: string | null
  committed_at?: string | null
  /** The five open pull requests updated last. */
  pulls?: PullRequest[]
}

export interface PullRequest {
  number: number
  title: string
  url: string
  draft: boolean
  updated_at: string | null
  ci: Repo['ci']
}

export interface ContributionDay {
  day: string
  count: number
  /** 0 to 4, GitHub's quartiles. */
  level: number
}

/** Your GitHub contribution calendar for the last 16 weeks, Monday first. */
export interface Activity {
  login: string
  total: number
  days: ContributionDay[]
  /** Set when GitHub failed; the days are then the last good ones. */
  error: string | null
}

export interface ReposResponse {
  as_of: string
  stale: boolean
  /** `own` is false for an owner listed only for your contributions (GEWIS). */
  groups: { login: string; label: string; repos: Repo[]; error: string | null; own?: boolean }[]
  /** One per configured token, by the owner labels it reads. */
  tokens?: GitHubToken[]
  activity?: Activity | null
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

/** Weather from Buienradar (GET /api/weather). */
export interface Weather {
  as_of: string
  stale: boolean
  station: string
  measured_at: string | null
  /** Buienradar's own words, in Dutch. */
  description: string | null
  temperature: number | null
  feel_temperature: number | null
  wind_bft: number | null
  wind_direction: string | null
  humidity: number | null
  rain_last_hour: number | null
  sunrise: string | null
  sunset: string | null
  /** The next 2 hours in 5-minute steps. */
  rain: { at: string; mm_per_hour: number }[]
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

/** /api/backups/restore-check: a check asked for from the Backups page (restore_request.py). */
export interface RestoreRequest {
  state: 'idle' | 'requested' | 'running'
  since: string | null
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
  late_minutes?: number
  offline_minutes?: number
  /** AdGuard Home not answering for this long. */
  minutes?: number
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

/** Worst first is "outage"; "unknown" means the status page has never answered. */
export type OutsideState = 'ok' | 'maintenance' | 'degraded' | 'outage' | 'unknown'

export interface OutsideIncident {
  title: string
  impact: 'maintenance' | 'degraded' | 'outage'
  status: string
  started_at: string | null
  url: string | null
  /** Oldest first, the last few. */
  updates: { at: string; status: string; text: string }[]
}

export interface OutsideService {
  key: string
  name: string
  url: string
  state: OutsideState
  incidents: OutsideIncident[]
  as_of: string
  /** The page could not be read; this is its last answer. */
  stale: boolean
  error: string | null
}

/** Outside services from their status pages (GET /api/outside-services). */
export interface OutsideServices {
  as_of: string
  stale: boolean
  services: OutsideService[]
}
