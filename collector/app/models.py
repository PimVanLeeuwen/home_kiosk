"""Response models for the API.

The kiosk models mirror the payloads in docs/kiosk-build-spec.md §5 exactly — they are the schema
contract the kiosk fixtures are written against, so change them deliberately. The Home hub models
follow at the end.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, SerializerFunctionWrapHandler, model_serializer


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


class RepoGroup(BaseModel):
    login: str
    label: str
    repos: list[Repo]
    # Short and safe to show; the repos are then the last good list, if any.
    error: str | None = None


class Repos(Envelope):
    groups: list[RepoGroup]


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


class BackupRun(BaseModel):
    started: datetime
    finished: datetime
    ok: bool
    volumes: list[BackupVolume]


class VolumeSummary(BaseModel):
    name: str
    last_run: BackupRun | None = None  # the newest run that included this volume
    last_success: datetime | None


class BackupHistory(Envelope):
    runs: list[BackupRun]  # newest first
    volumes: list[VolumeSummary]
    # The script sleeps 24 hours after each run, so the next one is due then.
    next_due: datetime | None
