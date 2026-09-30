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


def build(catalog: list[Service], container_cache: dict[str, Any] | None) -> Services:
    """Group the catalog in stored order and attach each service's status."""
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

    groups: dict[str, list[ServiceWithStatus]] = {}
    for service in catalog:
        groups.setdefault(service.group, []).append(
            ServiceWithStatus(
                **service.model_dump(), status=status_for(service.container, containers)
            )
        )

    return Services(
        as_of=as_of,
        stale=stale,
        groups=[ServiceGroup(name=name, services=items) for name, items in groups.items()],
    )


def seed(cfg: dict[str, Any]) -> list[Service]:
    """The default catalog from config.yaml, grouped as written."""
    catalog: list[Service] = []
    for group in cfg.get("services", []):
        for entry in group.get("items", []):
            catalog.append(Service(group=group["group"], **entry))
    return catalog
