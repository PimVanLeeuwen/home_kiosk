"""The service catalog behind the Services page, with a status per service.

The catalog lives in SQLite so it can be edited in the app; `config.yaml`
only seeds it on the first start. Status comes from the cached container list,
so this never touches the Docker socket on a request.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import (
    ContainerState,
    Service,
    ServiceGroup,
    Services,
    ServiceStatus,
    ServiceWithStatus,
)
from ..store import Store


def status_for(
    container: str | None, containers: dict[str, ContainerState] | None
) -> ServiceStatus:
    if not container or containers is None:
        return "unknown"
    state = containers.get(container)
    if state is None:
        return "missing"
    if state.state != "running":
        return "down"
    if state.health in ("unhealthy", "starting"):
        return state.health
    return "up"


def build(
    catalog: list[Service],
    container_cache: dict[str, Any] | None,
    widget_cache: dict[str, Any] | None = None,
) -> Services:
    """Group the catalog in stored order and attach each service's status and,
    where it has a widget, its latest stats."""
    containers: dict[str, ContainerState] | None = None
    as_of: datetime | None = None
    stale = True
    if container_cache:
        containers = {
            c["name"]: ContainerState.model_validate(c)
            for c in container_cache.get("containers", [])
        }
        as_of = datetime.fromisoformat(container_cache["as_of"])
        stale = bool(container_cache.get("stale"))

    widgets = (widget_cache or {}).get("items", {})

    groups: dict[str, list[ServiceWithStatus]] = {}
    for service in catalog:
        widget = widgets.get(service.id) if service.widget else None
        groups.setdefault(service.group, []).append(
            ServiceWithStatus(
                **service.model_dump(),
                status=status_for(service.container, containers),
                stats=widget.get("stats") if widget and not widget.get("error") else None,
                stats_error=widget.get("error") if widget else None,
            )
        )

    return Services(
        as_of=as_of,
        stale=stale,
        groups=[ServiceGroup(name=name, services=items) for name, items in groups.items()],
        stats_as_of=(widget_cache or {}).get("as_of"),
    )


def seed(cfg: dict[str, Any]) -> list[Service]:
    """The default catalog from config.yaml, grouped as written. Entries go
    through the same validation as edits in Settings."""
    from ..settings_api import ServiceInput  # noqa: PLC0415 (avoids an import cycle)

    catalog: list[Service] = []
    for group in cfg.get("services", []):
        for entry in group.get("items", []):
            fields = {k: v for k, v in entry.items() if k != "id"}
            checked = ServiceInput(group=group["group"], **fields)
            catalog.append(Service(id=entry["id"], **checked.model_dump()))
    return catalog


def prepare(store: Store, cfg: dict[str, Any]) -> str:
    """At startup: seed an empty catalog, or bring the default links into a
    catalog that was just upgraded to support them. Returns a log line."""
    defaults = seed(cfg)
    if store.seed_services(defaults):
        return "service catalog seeded from config.yaml"
    notes = []
    if store.catalog_upgraded:
        added = store.add_missing_services([s for s in defaults if s.url])
        notes.append(f"upgraded for links; added {', '.join(added) or 'none'}")
    if store.catalog_icons_added:
        filled = store.fill_missing_icons(defaults)
        if filled:
            notes.append(f"icons added for {len(filled)} entries")
    return f"service catalog {'; '.join(notes)}" if notes else "service catalog unchanged"
