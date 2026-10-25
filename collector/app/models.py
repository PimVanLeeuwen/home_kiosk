"""Response models for the API.

The kiosk models mirror the payloads in docs/kiosk-build-spec.md §5 exactly — they are the schema
contract the kiosk fixtures are written against, so change them deliberately. The Home hub models
follow at the end.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, PrivateAttr, SerializerFunctionWrapHandler, model_serializer


def _drop_none(data: dict, *keys: str) -> dict:
    """Remove keys whose value is None.

    The spec distinguishes "absent" from "null": an absent `next_earnings` means
    the view hides that cell, whereas a null `meta` means it falls back to
    `age_label`. Only the fields named here are allowed to disappear.
    """
    for key in keys:
        if data.get(key) is None:
            data.pop(key, None)
    return data


class Envelope(BaseModel):
    """Every response carries these, per the staleness rule."""

    as_of: datetime
    stale: bool = False


# --- /api/portfolio ----------------------------------------------------------


class PortfolioChange(BaseModel):
    day_abs: float
    day_pct: float
    month_pct: float
    year_pct: float
    all_pct: float


class HistoryPoint(BaseModel):
    d: str  # ISO date, e.g. "2026-08-19"
    v: float


class Holding(BaseModel):
    symbol: str
    name: str
    value: float
    day_pct: float
    weight_pct: float
    # Home hub additions; the kiosk ignores them.
    data_source: str | None = None
    isin: str | None = None
    currency: str | None = None
    quantity: float | None = None
    price: float | None = None
    day_abs: float | None = None
    invested: float | None = None
    gain_abs: float | None = None
    gain_pct: float | None = None


class AllocationSlice(BaseModel):
    label: str
    pct: float


class Portfolio(Envelope):
    currency: str
    total_value: float
    change: PortfolioChange
    history: list[HistoryPoint] = []
    holdings: list[Holding] = []
    allocation: list[AllocationSlice] = []
    # Home hub additions: since the first purchase, with currency effects.
    invested: float | None = None
    gain_abs: float | None = None
    cash: float | None = None
    dividends: float | None = None


# --- /api/spotlight ----------------------------------------------------------


class Range(BaseModel):
    low: float
    high: float


class Position(BaseModel):
    shares: float
    avg_cost: float
    invested: float | None = None
    value: float
    unrealised_abs: float
    unrealised_pct: float
    weight_pct: float
    held_since: str  # "2023-03"


class Spotlight(Envelope):
    symbol: str
    name: str
    exchange: str
    price: float
    currency: str
    day_abs: float
    day_pct: float
    history: list[HistoryPoint] = []
    # Intraday high/low. Ghostfolio only stores daily closes, so this is absent
    # when it is the source — omitted rather than faked from the close.
    day_range: Range | None = None
    range_52w: Range
    position: Position
    next_earnings: str | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict:
        # Omitted entirely when unknown so the view hides the cell rather than
        # rendering a dash.
        return _drop_none(handler(self), "next_earnings", "day_range")


# --- /api/news ---------------------------------------------------------------


class NewsItem(BaseModel):
    title: str
    source: str
    published: datetime
    age_label: str
    url: str
    meta: str | None = None
    # The untruncated title, for the Home hub's article store; not part of
    # the kiosk payload.
    _full_title: str = PrivateAttr(default="")
    # For Headlines, kept in the article store only.
    _image: str | None = PrivateAttr(default=None)
    _summary: str | None = PrivateAttr(default=None)


class NewsGroup(BaseModel):
    id: str
    title: str
    new_count: int = 0
    items: list[NewsItem] = []


class News(Envelope):
    groups: list[NewsGroup] = []
    # Total feeds polled, for the "N FEEDS · PULLED HH:MM" footer. Counted from
    # config rather than derived from groups, so feeds that returned nothing are
    # still reflected.
    feed_count: int = 0


# --- /api/nas ----------------------------------------------------------------


class Pool(BaseModel):
    """One UGOS volume. The view renders a bar per pool.

    An aggregate alone would hide a single pool filling up, which is the case
    the storage card exists to catch.
    """

    name: str
    used_bytes: int
    total_bytes: int
    used_pct: float
    free_bytes: int
    projection_months: float | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict:
        # Omitted when there is under a week of history, or usage is flat.
        return _drop_none(handler(self), "projection_months")


class Storage(BaseModel):
    used_bytes: int
    total_bytes: int
    used_pct: float
    free_bytes: int
    pools: list[Pool] = []
    projection_months: float | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> dict:
        # Omitted when there is under a week of history to project from.
        return _drop_none(handler(self), "projection_months")


class Containers(BaseModel):
    running: int
    total: int


class Disk(BaseModel):
    name: str
    temp_c: float | None = None
    smart: Literal["ok", "warn", "fail"]


class NetworkPoint(BaseModel):
    t: datetime
    rx: float
    tx: float


class Network(BaseModel):
    rx_mbps: float
    tx_mbps: float
    history: list[NetworkPoint] = []


class Backup(BaseModel):
    status: Literal["ok", "warn", "fail", "unknown"]
    at: datetime | None = None


class Nas(Envelope):
    host: str
    uptime_seconds: int
    storage: Storage
    cpu_pct: float
    ram_pct: float
    cpu_temp_c: float | None = None
    containers: Containers
    disks: list[Disk] = []
    network: Network
    backup: Backup
    # Added for the Home hub NAS page; the kiosk ignores it.
    mem_total_bytes: int | None = None


class NasPoint(BaseModel):
    """One 10-minute average on the NAS page charts."""

    t: datetime
    cpu: float | None
    ram: float | None
    temp: float | None
    rx_mbps: float | None
    tx_mbps: float | None


# --- Home hub: containers and services ----------------------------------------


class TailscaleHost(BaseModel):
    dns_name: str  # e.g. "dev-minotaur.tail1234.ts.net", no trailing dot
    ip: str | None  # the node's IPv4 in 100.64.0.0/10
    # `tailscale serve` HTTPS ports by the local port they proxy to, e.g.
    # {"8096": 18096, "8083": 443}. Empty when nothing is served.
    https_ports: dict[str, int] = {}


class Hosts(Envelope):
    """Where the NAS can be reached, for building service links."""

    lan: str
    tailscale: TailscaleHost


class TailnetDevice(BaseModel):
    name: str  # host name, e.g. "pim-macbook"
    dns_name: str  # MagicDNS name, no trailing dot
    os: str  # as tailscaled reports it: "macOS", "iOS", "linux", "windows", ...
    ipv4: str | None
    ipv6: str | None
    online: bool
    last_seen: datetime | None  # offline devices only
    # direct: a peer-to-peer path; relay: through a DERP relay; idle: online,
    # but no recent traffic, so no path yet. None for the NAS itself.
    connection: Literal["direct", "relay", "idle"] | None
    relay: str | None  # DERP region code, e.g. "ams": the relay in use, or the NAS's home relay
    endpoint: str | None  # ip:port of a direct path
    exit_node: bool  # offers itself as an exit node
    rx_bytes: int = 0
    tx_bytes: int = 0


class Tailnet(Envelope):
    """The NAS's tailnet: every device, how it connects, and tailscaled's health."""

    name: str  # the MagicDNS suffix's first label, e.g. "tail1234"; never the owner's login
    self: TailnetDevice
    peers: list[TailnetDevice]  # online first, then by name
    health: list[str]  # tailscaled's own warnings; empty when all checks pass


# --- /api/train ---------------------------------------------------------------


class TrainStop(BaseModel):
    name: str
    planned: datetime  # departure, or arrival at the last stop
    actual: datetime | None
    track: str | None  # the actual track, else the planned one
    cancelled: bool = False


class TrainRun(BaseModel):
    name: str  # "IC 3522"
    # late: one minute or more behind; not_found: NS's planner no longer lists it.
    status: Literal["on_time", "late", "cancelled", "not_found"]
    planned_departure: datetime
    actual_departure: datetime | None
    delay_minutes: int = 0
    planned_track: str | None = None
    actual_track: str | None = None
    stops: list[TrainStop] = []  # where it halts, from the first to the last of the route


class TrainDisruption(BaseModel):
    id: str
    kind: str  # NS's type: DISRUPTION or MAINTENANCE
    title: str  # NS's own words, e.g. "Utrecht - Amsterdam."
    text: str  # what happens, e.g. "minder treinen"
    until: str | None = None  # NS's own sentence about the expected end


class Train(Envelope):
    """The owner's weekday morning train, followed from the watch window until it leaves."""

    date: str  # the local date of the train this is about, YYYY-MM-DD
    route: str  # "Leiden Centraal to Rotterdam Centraal"
    departure: str = ""  # the planned departure followed, "07:16", even when NS drops it
    # morning: that day's train, until it leaves; evening: tomorrow's, checked the
    # evening before; idle: nothing to follow (night, weekend, midday).
    mode: Literal["morning", "evening", "idle"] = "idle"
    # The card shows and alerts run: in the morning until it leaves, in the
    # evening only when tomorrow's train has a problem.
    watching: bool
    departed: bool  # gone (or its replacement gone)
    train: TrainRun | None
    next_direct: TrainRun | None = None  # only when the train itself does not run
    disruptions: list[TrainDisruption] = []
    # UIC codes of every station the train passes between the two ends, for
    # matching disruptions; read once a day from NS's journey details.
    route_codes: list[str] = []
    checked_at: datetime | None = None  # the last call to NS


class ContainerState(BaseModel):
    name: str
    state: str  # Docker's State: running, exited, restarting, paused, created, dead
    health: Literal["healthy", "unhealthy", "starting"] | None = None
    # Extra detail for the Docker page; defaults keep older cached lists valid.
    id: str = ""
    image: str = ""
    image_id: str = ""
    project: str | None = None  # docker compose project, i.e. the stack
    status: str = ""  # Docker's human status, e.g. "Up 3 days (healthy)"
    # The image's OCI labels, which Docker copies onto the container (update notes, M26).
    version: str | None = None
    source: str | None = None


class ContainerList(Envelope):
    containers: list[ContainerState]


ServiceStatus = Literal["up", "starting", "unhealthy", "down", "missing", "unknown"]


class Service(BaseModel):
    id: str
    name: str
    group: str
    description: str = ""
    # A NAS service has a port (and path); an external link has a url instead.
    port: int | None = None
    path: str = "/"
    url: str | None = None
    container: str | None = None
    widget: str | None = None
    # A bundled icon (web/src/assets/icons/<icon>.svg or .png); letters when unset.
    icon: str | None = None


class Stat(BaseModel):
    label: str
    value: float
    unit: Literal["count", "bytes", "bytes_per_second", "percent"] = "count"


class WidgetResult(BaseModel):
    stats: list[Stat] = []
    # Short and safe to show: never contains a key or a URL with one.
    error: str | None = None


class WidgetStats(Envelope):
    items: dict[str, WidgetResult]  # by service id


class ServiceWithStatus(Service):
    status: ServiceStatus
    stats: list[Stat] | None = None
    stats_error: str | None = None


class ServiceGroup(BaseModel):
    name: str
    services: list[ServiceWithStatus]


class Services(BaseModel):
    # Status comes from the container list, which may not exist yet on a cold
    # start; the catalog itself is always there.
    as_of: datetime | None
    stale: bool
    groups: list[ServiceGroup]
    stats_as_of: datetime | None = None


# --- Home hub: GitHub repos ----------------------------------------------------


class Release(BaseModel):
    tag: str
    published_at: datetime | None
    url: str


class PullRequest(BaseModel):
    number: int
    title: str
    url: str
    draft: bool
    updated_at: datetime | None
    # Combined check state of its latest commit.
    ci: Literal["passing", "failing", "running", "none"]


class Repo(BaseModel):
    name: str
    full_name: str
    url: str
    description: str | None
    private: bool
    fork: bool
    language: str | None
    language_color: str | None
    stars: int
    forks: int
    pushed_at: datetime | None
    open_prs: int
    open_issues: int
    # Combined check state of the default branch's latest commit.
    ci: Literal["passing", "failing", "running", "none"]
    release: Release | None
    # The default branch and its latest commit, for the Code card.
    branch: str | None = None
    commit_message: str | None = None
    committed_at: datetime | None = None
    pulls: list[PullRequest] = []  # the five open pull requests updated last


class RepoGroup(BaseModel):
    login: str
    label: str
    repos: list[Repo]
    # Short and safe to show; the repos are then the last good list, if any.
    error: str | None = None
    # False for an owner listed only for your contributions (GEWIS): its builds
    # and pull requests are other people's, so the Code card leaves them out.
    own: bool = True


class GitHubToken(BaseModel):
    """One configured token; the value itself is never kept."""

    owners: list[str]  # labels of the owners it reads, e.g. ["Mine", "GEWIS"]
    expires_at: datetime | None = None  # None: no expiry date, or not known yet
    checked: bool = False  # GitHub has answered a request with it


class ContributionDay(BaseModel):
    day: date
    count: int
    level: int  # 0 to 4, GitHub's quartiles


class Activity(BaseModel):
    """Your GitHub contribution calendar for the last 16 weeks, Monday first."""

    login: str
    total: int
    days: list[ContributionDay]  # from a Monday up to today
    error: str | None = None  # then the days are the last good ones


class Repos(Envelope):
    groups: list[RepoGroup]
    tokens: list[GitHubToken] = []
    activity: Activity | None = None


# --- Home hub: Docker page ------------------------------------------------------


class ContainerLoad(BaseModel):
    name: str
    project: str | None
    image: str
    state: str
    health: Literal["healthy", "unhealthy", "starting"] | None
    status: str
    # None until two readings exist (CPU and network are rates), or when stopped.
    cpu_pct: float | None
    mem_bytes: int | None
    mem_limit: int | None
    rx_bps: float | None  # bytes per second
    tx_bps: float | None


class DockerOverview(Envelope):
    containers: list[ContainerLoad]
    cpu_pct: float  # all containers together, as a share of the whole machine
    mem_bytes: int


class ContainerPoint(BaseModel):
    t: datetime
    cpu: float | None
    mem: int | None


class ContainerUpdate(BaseModel):
    at: datetime
    name: str
    image: str
    old_image_id: str
    new_image_id: str


# --- Home hub: backups ------------------------------------------------------------


class BackupVolume(BaseModel):
    name: str
    ok: bool
    exit_code: int
    seconds: int
    # From rclone's final stats; None when the run left no stats line.
    bytes: int | None = None
    transfers: int | None = None
    checks: int | None = None
    deletes: int | None = None
    errors: int | None = None
    last_error: str | None = None


class StorageUse(BaseModel):
    """Space on the Hetzner storage box after a run, from `rclone about`."""

    total: int
    used: int
    free: int


class BackupRun(BaseModel):
    started: datetime
    finished: datetime
    ok: bool
    volumes: list[BackupVolume]
    storage: StorageUse | None = None  # runs before backup.sh recorded it have none


class StorageBox(StorageUse):
    used_pct: float
    at: datetime  # the run that measured it
    # Months until full at the growth rate seen over recent runs; None when
    # there is too little history or usage is not growing.
    projection_months: float | None = None


class VolumeSummary(BaseModel):
    name: str
    last_run: BackupRun | None = None  # the newest run that included this volume
    last_success: datetime | None


class BackupHistory(Envelope):
    runs: list[BackupRun]  # newest first
    volumes: list[VolumeSummary]
    # The next scheduled start after the last run (BACKUP_AT, see schedule.sh).
    next_due: datetime | None
    storage_box: StorageBox | None = None


# --- Home hub: GitHub mirror ----------------------------------------------------


class MirroredRepo(BaseModel):
    full_name: str
    archived: bool = False
    # This run's result; `mirrored_at` is the last time it succeeded.
    ok: bool
    error: str | None = None
    mirrored_at: datetime | None = None
    bytes: int | None = None


class MirrorOwner(BaseModel):
    login: str
    label: str
    repos: list[MirroredRepo]
    # Mirrors deleted this run because the repo is gone from GitHub.
    removed: list[str] = []
    # Listing the owner failed: nothing was fetched or removed for it.
    error: str | None = None


class MirrorRun(BaseModel):
    started: datetime
    finished: datetime
    ok: bool
    repos: int
    failed: int
    removed: int
    bytes: int


class GitHubMirror(Envelope):
    # Off when no owner in config.yaml has `mirror: true`.
    enabled: bool
    dir: str
    # Set when the whole run could not start, such as a missing mount.
    error: str | None = None
    owners: list[MirrorOwner] = []
    runs: list[MirrorRun] = []  # newest first
    last_success: datetime | None = None  # the last run with every repo mirrored
    next_due: datetime | None = None


# --- Home hub: database copy for the backup --------------------------------------


class DatabaseCopy(Envelope):
    # The last nightly copy of the hub's own SQLite file.
    ok: bool
    path: str
    bytes: int | None = None
    error: str | None = None
    last_success: datetime | None = None


# --- Home hub: database dumps -----------------------------------------------------


class DumpedDatabase(BaseModel):
    name: str  # ghostfolio, tandoor, tracearr, hub
    label: str
    kind: Literal["pg_dump", "sqlite"]
    ok: bool | None  # the newest attempt; None when there is none yet
    at: datetime | None = None  # when the newest attempt finished
    bytes: int | None = None
    error: str | None = None
    last_success: datetime | None = None


class DumpRun(BaseModel):
    started: datetime
    finished: datetime
    ok: bool
    failed: int


class RestoreCheckItem(BaseModel):
    name: str  # download:databases, download:hub, ghostfolio, hub
    ok: bool
    detail: str


class RestoreCheck(BaseModel):
    started: datetime
    finished: datetime
    ok: bool
    checks: list[RestoreCheckItem]


class DatabaseDumps(Envelope):
    databases: list[DumpedDatabase]
    runs: list[DumpRun]  # the host job's runs, newest first
    # The monthly restore check (host-jobs/restore-check.sh), newest first.
    restore_checks: list[RestoreCheck] = []
    last_verified: datetime | None = None  # the newest check that passed


# --- Home hub: UPS ----------------------------------------------------------------


class UpsOutage(BaseModel):
    started_at: datetime  # when the hub first saw the UPS on battery
    ended_at: datetime | None = None  # when it saw mains again; None while it lasts
    lowest_charge: int | None = None
    # The charge reached battery.charge.low, where UGOS stops all services.
    reached_low: bool = False


class Ups(Envelope):
    name: str
    model: str | None = None
    status: Literal["online", "on_battery", "low_battery", "unknown"]
    status_raw: str  # NUT's ups.status, such as "OL" or "OB LB"
    charge: int | None = None
    charge_low: int | None = None
    load: int | None = None  # percent
    outages: list[UpsOutage] = []  # newest first; the first is open while it lasts


# --- Home hub: exposure audit -------------------------------------------------------


class PublicHost(BaseModel):
    hostname: str
    source: Literal["tunnel", "dns"]  # a tunnel route, or a DNS record on the house
    target: str  # the tunnel's service, or the DNS record's content
    allowed: bool  # on the allowlist in config.yaml
    status: int | None = None  # the HTTPS answer from outside; None when there was none
    error: str | None = None


class Exposure(Envelope):
    zone: str
    home_ip: str | None = None
    hosts: list[PublicHost] = []
    # The audit could not run (no token, Cloudflare refused); hosts are then
    # the last known list.
    error: str | None = None


class PortScanRun(BaseModel):
    """One nightly scan of the home IP from outside (the exposure-scan workflow)."""

    started: datetime
    finished: datetime
    ports_checked: int
    open: list[int]  # TCP ports that accepted a connection
    error: str | None = None  # the scan could not run


class PortScan(Envelope):
    runs: list[PortScanRun]  # newest first


# --- Home hub: weather ------------------------------------------------------------


class RainPoint(BaseModel):
    at: datetime
    mm_per_hour: float


class Weather(Envelope):
    station: str
    measured_at: datetime | None = None
    description: str | None = None  # Buienradar's own words, in Dutch
    temperature: float | None = None
    feel_temperature: float | None = None
    wind_bft: int | None = None
    wind_direction: str | None = None
    humidity: float | None = None
    rain_last_hour: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    rain: list[RainPoint] = []  # the next 2 hours in 5-minute steps


# --- Home hub: the living room's air (/api/air) ------------------------------------


class AirPoint(BaseModel):
    at: datetime
    co2: int  # ppm


class AirState(Envelope):
    room: str
    available: bool = True  # the Matter server can reach the sensor
    temperature: float | None = None  # °C, one decimal
    humidity: int | None = None  # %
    co2: int | None = None  # ppm
    pm25: int | None = None  # µg/m³
    quality: str | None = None  # the sensor's own verdict: "Good" to "Extremely poor"
    level: Literal["fresh", "stuffy", "open_window"] | None = None  # by CO2
    outside: int | None = None  # °C, from Buienradar
    history: list[AirPoint] = []  # CO2 every 5 minutes, the last 8 hours


class DocumentHit(BaseModel):
    id: int
    title: str
    correspondent: str | None = None
    created: str | None = None  # YYYY-MM-DD


class DocumentSearch(Envelope):
    """Paperless's full-text search for the command palette (documents_api.py)."""
    available: bool = True
    reason: str | None = None
    results: list[DocumentHit] = []


class DnsHour(BaseModel):
    queries: int
    blocked: int


class DnsStats(Envelope):
    """AdGuard Home's last 24 hours (sources/adguard.py): totals only, never per device."""
    answering: bool = True  # False once AdGuard has failed for a few minutes
    failing: Literal["dns", "admin"] | None = None  # which part does not answer
    failing_since: datetime | None = None
    protection: bool = True  # blocking on (AdGuard can pause it)
    queries: int
    blocked: int
    share: float | None = None  # percent blocked; None before any query
    hours: list[DnsHour] = []  # oldest first, the last one is the current hour
    top_blocked: str | None = None
    top_blocked_count: int | None = None


# --- Home hub: pipelines (/api/pipelines) ----------------------------------------

JobState = Literal["done", "running", "queued", "approval", "failed", "cancelled"]


class PipelineJob(BaseModel):
    """One job of the workflow (a matrix job counts once, `count` times)."""
    key: str  # the workflow file's job id
    name: str  # without its matrix part: "Build & push"
    column: int  # its stage: 0 for jobs that need nothing
    needs: list[str] = []
    state: JobState
    count: int = 1
    seconds: int | None = None  # how long it took, or has been running
    progress: float | None = None  # 0 to 1 while running, from its last good run


class PipelineRun(BaseModel):
    number: int
    url: str
    state: Literal["running", "approval", "success", "failure", "cancelled"]
    started_at: datetime
    ended_at: datetime | None = None
    approval_since: datetime | None = None  # waiting at an approval gate since
    seconds: int  # so far, or in all
    usual: list[int] = []  # the shortest and longest of the last good runs, seconds
    commit: str = ""  # its message's first line
    author: str | None = None
    sha: str = ""  # short
    failed: str | None = None  # the first failed job's name
    jobs: list[PipelineJob] = []


class PipelineRecent(BaseModel):
    ok: bool
    seconds: int
    at: datetime


class PipelineRepo(BaseModel):
    repo: str  # "owner/name"
    name: str  # "home_kiosk"
    branch: str
    recent: list[PipelineRecent] = []  # the last finished runs, oldest first
    run: PipelineRun | None = None  # the latest, while it runs or for a while after


class Pipelines(Envelope):
    repos: list[PipelineRepo] = []


# --- Home hub: outside services ---------------------------------------------------

# Worst first is "outage"; "unknown" means the status page has never answered.
OutsideState = Literal["ok", "maintenance", "degraded", "outage", "unknown"]


class OutsideUpdate(BaseModel):
    at: datetime
    status: str  # the page's own word: investigating, identified, monitoring, ...
    text: str


class OutsideIncident(BaseModel):
    title: str
    impact: Literal["maintenance", "degraded", "outage"]
    status: str
    started_at: datetime | None = None
    url: str | None = None
    updates: list[OutsideUpdate] = []  # oldest first, the last few


class OutsideService(BaseModel):
    key: str
    name: str
    url: str  # the public status page
    state: OutsideState
    incidents: list[OutsideIncident] = []
    # Each page is fetched on its own: one that fails keeps its last answer,
    # flagged stale with the reason.
    as_of: datetime
    stale: bool = False
    error: str | None = None


class OutsideServices(Envelope):
    services: list[OutsideService]
