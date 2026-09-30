"""Settings endpoints: editing the service catalog in the app.

All writes go through `same_origin_json`; see security.py. Validation lives in
the input models, so a bad request is a 422 with a readable reason.
"""

from __future__ import annotations

import re
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from .models import Service
from .security import same_origin_json
from .sources import widgets
from .store import Store

router = APIRouter(prefix="/api/settings")
write = [Depends(same_origin_json)]

# The widget types that have an adapter.
WIDGETS = sorted(widgets.REGISTRY)

_CONTAINER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

Text = Annotated[str, Field(min_length=1, max_length=60)]


class ServiceInput(BaseModel):
    name: Text
    group: Annotated[str, Field(min_length=1, max_length=40)]
    description: Annotated[str, Field(max_length=80)] = ""
    # Either a NAS service (port, path, optional container and widget) or an
    # external link (url only).
    port: Annotated[int | None, Field(ge=1, le=65535)] = None
    path: Annotated[str, Field(max_length=200)] = "/"
    url: Annotated[str | None, Field(max_length=500)] = None
    container: Annotated[str | None, Field(max_length=128)] = None
    widget: str | None = None
    # Name of a bundled icon; the web app falls back to letters if it has none.
    icon: Annotated[str | None, Field(max_length=40)] = None

    @field_validator("name", "group", "description")
    @classmethod
    def _trim(cls, value: str) -> str:
        value = " ".join(value.split())
        return value

    @field_validator("name", "group")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        value = value.strip() or "/"
        if not value.startswith("/"):
            value = "/" + value
        if any(c.isspace() for c in value) or "\\" in value:
            raise ValueError("must be a URL path without spaces, like /_utils")
        return value

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        parts = urlsplit(value)
        # http(s) only: a javascript: or data: URL would run in the hub's page.
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("must be a full http:// or https:// address")
        return value

    @model_validator(mode="after")
    def _service_or_link(self) -> ServiceInput:
        if (self.port is None) == (self.url is None):
            raise ValueError("give either a port (NAS service) or a url (link), not both")
        if self.url is not None:
            if self.container or self.widget:
                raise ValueError("a link has no container or widget")
            self.path = "/"
        return self

    @field_validator("container")
    @classmethod
    def _container(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if not _CONTAINER.match(value):
            raise ValueError("must be a Docker container name")
        return value

    @field_validator("icon")
    @classmethod
    def _icon(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not _ID.match(value):
            raise ValueError("must be an icon name like jellyfin or uptime-kuma")
        return value

    @field_validator("widget")
    @classmethod
    def _widget(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value not in WIDGETS:
            raise ValueError(f"must be one of: {', '.join(WIDGETS)}")
        return value


class NewService(ServiceInput):
    # Optional: derived from the name when left out.
    id: Annotated[str | None, Field(max_length=40)] = None


class Order(BaseModel):
    ids: list[str]


class GroupRename(BaseModel):
    old: Text
    new: Annotated[str, Field(min_length=1, max_length=40)]


def _store(request: Request) -> Store:
    return request.app.state.store


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-") or "service"


def _catalog(store: Store) -> dict[str, Any]:
    return {"services": store.list_services(), "widgets": WIDGETS}


@router.get("/services")
def list_catalog(request: Request) -> dict[str, Any]:
    """The editable catalog, without status, plus the widget choices."""
    return _catalog(_store(request))


@router.post("/services", status_code=201, dependencies=write)
def add_service(body: NewService, request: Request) -> dict[str, Any]:
    store = _store(request)
    taken = {s.id for s in store.list_services()}
    if body.id:
        if not _ID.match(body.id):
            raise HTTPException(422, "id: use lowercase letters, digits and dashes")
        if body.id in taken:
            raise HTTPException(409, f"A service with id {body.id} already exists.")
        new_id = body.id
    else:
        base = slug(body.name)
        new_id, n = base, 2
        while new_id in taken:
            new_id, n = f"{base}-{n}", n + 1
    store.add_service(Service(id=new_id, **body.model_dump(exclude={"id"})))
    return _catalog(store)


@router.put("/services/{service_id}", dependencies=write)
def update_service(service_id: str, body: ServiceInput, request: Request) -> dict[str, Any]:
    store = _store(request)
    if not store.update_service(Service(id=service_id, **body.model_dump())):
        raise HTTPException(404, "No such service.")
    return _catalog(store)


@router.delete("/services/{service_id}", dependencies=write)
def delete_service(service_id: str, request: Request) -> dict[str, Any]:
    store = _store(request)
    if not store.delete_service(service_id):
        raise HTTPException(404, "No such service.")
    return _catalog(store)


@router.put("/services-order", dependencies=write)
def reorder(body: Order, request: Request) -> dict[str, Any]:
    """Apply a complete new order. Groups follow their first service, so this
    also reorders groups."""
    store = _store(request)
    current = {s.id for s in store.list_services()}
    if len(body.ids) != len(set(body.ids)) or set(body.ids) != current:
        raise HTTPException(409, "The order must list every service exactly once.")
    store.reorder_services(body.ids)
    return _catalog(store)


@router.put("/groups", dependencies=write)
def rename_group(body: GroupRename, request: Request) -> dict[str, Any]:
    store = _store(request)
    new = " ".join(body.new.split())
    if not new:
        raise HTTPException(422, "new: must not be blank")
    if not store.rename_group(body.old, new):
        raise HTTPException(404, "No such group.")
    return _catalog(store)
