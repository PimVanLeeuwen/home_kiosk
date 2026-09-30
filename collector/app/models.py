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


# --- Home hub: containers and services ----------------------------------------


class TailscaleHost(BaseModel):
    dns_name: str  # e.g. "dev-minotaur.tail1234.ts.net", no trailing dot
    ip: str | None  # the node's IPv4 in 100.64.0.0/10


class Hosts(Envelope):
    """Where the NAS can be reached, for building service links."""

    lan: str
    tailscale: TailscaleHost


class ContainerState(BaseModel):
    name: str
    state: str  # Docker's State: running, exited, restarting, paused, created, dead
    health: Literal["healthy", "unhealthy", "starting"] | None = None


class ContainerList(Envelope):
    containers: list[ContainerState]


ServiceStatus = Literal["up", "starting", "unhealthy", "down", "missing", "unknown"]


class Service(BaseModel):
    id: str
    name: str
    group: str
    description: str = ""
    port: int
    path: str = "/"
    container: str | None = None
    widget: str | None = None


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
