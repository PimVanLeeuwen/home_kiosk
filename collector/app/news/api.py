"""Endpoints for the News page and for editing feeds in Settings."""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from ..security import same_origin_json
from . import reader
from . import store as news

router = APIRouter(prefix="/api")
write = [Depends(same_origin_json)]


def _store(request: Request):
    return request.app.state.store


# --- reading ---------------------------------------------------------------------------


@router.get("/news/groups")
def list_groups(request: Request) -> list[dict[str, Any]]:
    """The groups in order, with unread counts, for the News page filters."""
    unread = news.unread_counts(_store(request))
    return [{"id": g.id, "title": g.title, "unread": unread.get(g.id, 0)}
            for g in news.groups(_store(request))]


@router.get("/news/articles")
def list_articles(
    request: Request, group: str | None = None, unread: bool = False, q: str | None = None,
    limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    items, total = news.articles(
        _store(request), group=group, unread=unread, q=(q or "")[:100],
        limit=min(max(limit, 1), 200), offset=max(offset, 0))
    return {"articles": items, "total": total}


def _transport(request: Request):
    # Tests swap in a mock transport; production uses the network.
    return getattr(request.app.state, "reader_transport", None)


@router.get("/news/articles/{article_id}/content")
async def article_content(article_id: str, request: Request) -> dict[str, Any]:
    """The article as plain text blocks for the reader. When extraction fails
    the answer is {ok: false, reason}, and the page offers the original."""
    store = _store(request)
    found = news.article(store, article_id)
    if found is None:
        raise HTTPException(404, "No such article.")
    content = reader.cached(store, article_id)
    if content is None:
        content = await reader.extract(found.url, article_id, _transport(request))
        reader.remember(store, article_id, content)
    return content.model_dump(exclude={"images"})


@router.get("/news/articles/{article_id}/images/{index}")
async def article_image(article_id: str, index: int, request: Request) -> Response:
    """Only images found in the cached article, so this is not an open proxy."""
    content = reader.cached(_store(request), article_id)
    if content is None or not 0 <= index < len(content.images):
        raise HTTPException(404, "No such image.")
    try:
        data, kind = await reader.image(content.images[index], _transport(request))
    except Exception as exc:
        raise HTTPException(502, "The image could not be loaded.") from exc
    return Response(data, media_type=kind, headers={
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'",
    })


class ReadState(BaseModel):
    read: bool


@router.post("/news/articles/{article_id}/read", dependencies=write)
def set_read(article_id: str, body: ReadState, request: Request) -> dict[str, bool]:
    if not news.mark_read(_store(request), article_id, body.read):
        raise HTTPException(404, "No such article.")
    return {"read": body.read}


class ReadAll(BaseModel):
    group: str | None = None


@router.post("/news/read-all", dependencies=write)
def read_all(body: ReadAll, request: Request) -> dict[str, int]:
    return {"marked": news.mark_all_read(_store(request), body.group)}


# --- editing feeds -----------------------------------------------------------------------


def _check_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("must be a full http:// or https:// feed address")
    return value


class FeedInput(BaseModel):
    group_id: str
    url: Annotated[str, Field(max_length=500)]
    name: Annotated[str | None, Field(max_length=60)] = None

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        return _check_url(value)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        value = " ".join((value or "").split())
        return value or None


class GroupInput(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=40)]

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("must not be blank")
        return value


def _feeds(request: Request) -> list[news.FeedGroup]:
    return news.groups(_store(request))


@router.get("/settings/feeds")
def get_feeds(request: Request) -> list[news.FeedGroup]:
    return _feeds(request)


@router.post("/settings/feeds", status_code=201, dependencies=write)
def add_feed(body: FeedInput, request: Request) -> list[news.FeedGroup]:
    if news.add_feed(_store(request), body.group_id, body.url, body.name) is None:
        raise HTTPException(404, "No such group.")
    return _feeds(request)


@router.put("/settings/feeds/{feed_id}", dependencies=write)
def update_feed(feed_id: int, body: FeedInput, request: Request) -> list[news.FeedGroup]:
    if not news.update_feed(_store(request), feed_id, body.group_id, body.url, body.name):
        raise HTTPException(404, "No such feed or group.")
    return _feeds(request)


@router.delete("/settings/feeds/{feed_id}", dependencies=write)
def delete_feed(feed_id: int, request: Request) -> list[news.FeedGroup]:
    if not news.delete_feed(_store(request), feed_id):
        raise HTTPException(404, "No such feed.")
    return _feeds(request)


@router.post("/settings/feed-groups", status_code=201, dependencies=write)
def add_group(body: GroupInput, request: Request) -> list[news.FeedGroup]:
    news.add_group(_store(request), body.title)
    return _feeds(request)


@router.put("/settings/feed-groups/{group_id}", dependencies=write)
def rename_group(group_id: str, body: GroupInput, request: Request) -> list[news.FeedGroup]:
    if not news.rename_group(_store(request), group_id, body.title):
        raise HTTPException(404, "No such group.")
    return _feeds(request)


@router.delete("/settings/feed-groups/{group_id}", dependencies=write)
def delete_group(group_id: str, request: Request) -> list[news.FeedGroup]:
    """Removes the group and its feeds; its articles age out within a week."""
    if not news.delete_group(_store(request), group_id):
        raise HTTPException(404, "No such group.")
    return _feeds(request)
