"""Bring Ghostfolio up to date from a DEGIRO Transactions export.

Preview first, import on confirmation; both read the file afresh, so importing
twice adds nothing the second time.

- Symbols: DEGIRO names products by ISIN, Ghostfolio by data source and symbol,
  and Ghostfolio's profiles here carry no ISIN. The hub looks the ISIN up with
  Ghostfolio (`/api/v1/symbol/lookup`, Yahoo search underneath) and takes the
  listing you already hold. Without one it asks, and remembers the answer.
- Already there: the existing activities came from a CSV import without DEGIRO
  order IDs, so a trade counts as present when an unused activity has the same
  symbol, type, quantity and day, at a price within PRICE_TOLERANCE. Ghostfolio
  skips exact duplicates on import as well.

Contract checked against the Ghostfolio 3.76.0 source:

    GET  /api/v1/activities   -> {activities: [{accountId, date, type, quantity, unitPrice,
                                   comment, assetProfile{symbol, dataSource, name}}]}
    GET  /api/v1/account                 -> {accounts: [{id, name, platform?{name}}]}
    GET  /api/v1/symbol/lookup?query=    -> {items: [{symbol, dataSource, name, currency}]}
    POST /api/v1/import  {activities: [{accountId, comment, currency, dataSource, date, fee,
                                        quantity, symbol, type, unitPrice}]}
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from ..sources.ghostfolio import Client
from ..store import Store
from . import degiro
from .holding import DATA_SOURCE, SYMBOL, _client
from .holding import _cache as holding_cache

PRICE_TOLERANCE = 0.005
IMPORT_CHUNK = 100
IMPORT_TIMEOUT = 120

TABLES = """
CREATE TABLE IF NOT EXISTS degiro_symbol (
    isin        TEXT PRIMARY KEY,
    data_source TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    chosen_at   TEXT NOT NULL
);
"""


class Candidate(BaseModel):
    symbol: str
    data_source: str
    name: str
    currency: str | None = None
    held: bool = False


class Row(BaseModel):
    line: int
    date: datetime
    product: str
    isin: str
    type: str
    quantity: float
    price: float
    currency: str
    fee: float
    order_id: str
    status: Literal["new", "exists", "unknown"]
    symbol: str | None = None
    data_source: str | None = None


class Product(BaseModel):
    """An ISIN that needs a symbol before its trades can be imported."""

    isin: str
    product: str
    candidates: list[Candidate]


class Account(BaseModel):
    id: str
    name: str


class Preview(BaseModel):
    rows: list[Row]
    skipped: list[str]
    unknown: list[Product]
    accounts: list[Account]
    account_id: str | None
    counts: dict[str, int]


class Choice(BaseModel):
    data_source: str
    symbol: str


class DegiroError(Exception):
    """Something to tell the person importing; the message is a sentence."""


@dataclass
class _Existing:
    symbol: str
    data_source: str
    name: str
    type: str
    when: datetime
    quantity: float
    price: float
    used: bool = False


def ensure_tables(store: Store) -> None:
    with store.connect() as conn:
        conn.executescript(TABLES)


def saved_choices(store: Store) -> dict[str, Choice]:
    with store.connect() as conn:
        rows = conn.execute("SELECT isin, data_source, symbol FROM degiro_symbol").fetchall()
    return {r["isin"]: Choice(data_source=r["data_source"], symbol=r["symbol"]) for r in rows}


def save_choices(store: Store, choices: dict[str, Choice]) -> None:
    now = datetime.now(UTC).isoformat()
    with store.connect() as conn:
        conn.executemany(
            "INSERT INTO degiro_symbol (isin, data_source, symbol, chosen_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(isin) DO UPDATE SET data_source = excluded.data_source, "
            "symbol = excluded.symbol, chosen_at = excluded.chosen_at",
            [(isin, c.data_source, c.symbol, now) for isin, c in choices.items()])


def check_choices(choices: dict[str, Choice]) -> None:
    for isin, c in choices.items():
        if not DATA_SOURCE.match(c.data_source) or not SYMBOL.match(c.symbol) or len(isin) != 12:
            raise DegiroError(f"“{c.symbol}” is not a valid symbol for {isin}.")


# --- matching ------------------------------------------------------------------------------


def _existing(activities: list[dict[str, Any]]) -> list[_Existing]:
    out = []
    for a in activities:
        profile = a.get("assetProfile") or a.get("SymbolProfile") or {}
        if a.get("type") not in ("BUY", "SELL") or not profile.get("symbol"):
            continue
        out.append(_Existing(
            symbol=profile["symbol"], data_source=profile.get("dataSource") or "",
            name=profile.get("name") or profile["symbol"], type=a["type"],
            when=datetime.fromisoformat(a["date"].replace("Z", "+00:00")),
            quantity=float(a.get("quantity") or 0), price=float(a.get("unitPrice") or 0),
        ))
    return out


def _same_day(trade: degiro.Trade, existing: _Existing) -> bool:
    """Imports differ in how they store the time, so either calendar day counts."""
    return trade.day in (existing.when.astimezone(UTC).date(),
                         existing.when.astimezone(degiro.AMSTERDAM).date())


def find_match(trade: degiro.Trade, choice: Choice, existing: list[_Existing]) -> _Existing | None:
    for e in existing:
        if (
            not e.used
            and e.symbol == choice.symbol
            and e.data_source == choice.data_source
            and e.type == trade.type
            and abs(e.quantity - trade.quantity) < 1e-6
            and abs(e.price - trade.price) <= PRICE_TOLERANCE * max(trade.price, 1e-9)
            and _same_day(trade, e)
        ):
            return e
    return None


# --- Ghostfolio ----------------------------------------------------------------------------


def _default_account(
    accounts: list[dict[str, Any]], activities: list[dict[str, Any]]
) -> str | None:
    for a in accounts:
        names = f"{a.get('name') or ''} {(a.get('platform') or {}).get('name') or ''}".lower()
        if "degiro" in names:
            return a["id"]
    used = Counter(a.get("accountId") for a in activities if a.get("accountId"))
    if used:
        return used.most_common(1)[0][0]
    return accounts[0]["id"] if accounts else None


async def _lookup(client: Client, http: httpx.AsyncClient, isin: str,
                  held: set[tuple[str, str]]) -> list[Candidate]:
    try:
        found = await client.get(http, "/api/v1/symbol/lookup", query=isin)
    except Exception:
        return []
    return [
        Candidate(symbol=i["symbol"], data_source=i["dataSource"],
                  name=i.get("name") or i["symbol"], currency=i.get("currency"),
                  held=(i["dataSource"], i["symbol"]) in held)
        for i in found.get("items") or []
        if i.get("symbol") and i.get("dataSource")
    ]


async def preview(cfg: dict[str, Any], store: Store, text: str,
                  choices: dict[str, Choice] | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> Preview:
    trades, skipped = degiro.parse(text)
    if not trades:
        raise DegiroError("The file has no trades in it.")
    client = _client(cfg)
    chosen = {**saved_choices(store), **(choices or {})}

    async with httpx.AsyncClient(transport=transport) as http:
        activities = (await client.get(http, "/api/v1/activities", sortColumn="date",
                                       sortDirection="asc")).get("activities") or []
        accounts = (await client.get(http, "/api/v1/account")).get("accounts") or []
        existing = _existing(activities)
        held = {(e.data_source, e.symbol) for e in existing}
        names = {(e.data_source, e.symbol): e.name for e in existing}

        unknown: list[Product] = []
        to_look_up = sorted({t.isin for t in trades if t.isin not in chosen})
        found = await asyncio.gather(*(_lookup(client, http, i, held) for i in to_look_up))
        for isin, candidates in zip(to_look_up, found, strict=True):
            owned = [c for c in candidates if c.held]
            if len(owned) == 1:
                chosen[isin] = Choice(data_source=owned[0].data_source, symbol=owned[0].symbol)
            else:
                product = next(t.product for t in trades if t.isin == isin)
                # Offer what Yahoo found, then everything you hold to pick from.
                extra = [Candidate(symbol=s, data_source=ds, name=names[(ds, s)], held=True)
                         for ds, s in sorted(held)
                         if (ds, s) not in {(c.data_source, c.symbol) for c in candidates}]
                unknown.append(Product(isin=isin, product=product, candidates=candidates + extra))

    rows = []
    for t in trades:
        choice = chosen.get(t.isin)
        if choice is None:
            status = "unknown"
        else:
            match = find_match(t, choice, existing)
            if match:
                match.used = True
            status = "exists" if match else "new"
        rows.append(Row(
            line=t.line, date=t.when, product=t.product, isin=t.isin, type=t.type,
            quantity=t.quantity, price=t.price, currency=t.currency, fee=t.fee,
            order_id=t.order_id, status=status,
            symbol=choice.symbol if choice else None,
            data_source=choice.data_source if choice else None,
        ))
    counts = Counter(r.status for r in rows)
    return Preview(
        rows=rows, skipped=skipped, unknown=unknown,
        accounts=[Account(id=a["id"], name=a.get("name") or a["id"]) for a in accounts],
        account_id=_default_account(accounts, activities),
        counts={k: counts.get(k, 0) for k in ("new", "exists", "unknown")},
    )


def activity(row: Row, account_id: str) -> dict[str, Any]:
    return {
        "accountId": account_id,
        "comment": f"DEGIRO order {row.order_id}" if row.order_id else "DEGIRO",
        "currency": row.currency,
        "dataSource": row.data_source,
        "date": row.date.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "fee": row.fee,
        "quantity": row.quantity,
        "symbol": row.symbol,
        "type": row.type,
        "unitPrice": row.price,
    }


async def run_import(cfg: dict[str, Any], store: Store, text: str, account_id: str,
                     choices: dict[str, Choice],
                     transport: httpx.AsyncBaseTransport | None = None) -> dict[str, int]:
    """Import the rows that are new. Your symbol choices are remembered first."""
    check_choices(choices)
    result = await preview(cfg, store, text, choices, transport)
    if account_id not in {a.id for a in result.accounts}:
        raise DegiroError("Choose the Ghostfolio account to import into.")
    save_choices(store, choices)

    new = [activity(r, account_id) for r in result.rows if r.status == "new"]
    client = _client(cfg)
    async with httpx.AsyncClient(transport=transport) as http:
        for start in range(0, len(new), IMPORT_CHUNK):
            await client.post(http, "/api/v1/import",
                              {"activities": new[start:start + IMPORT_CHUNK]},
                              timeout=IMPORT_TIMEOUT)
    holding_cache.clear()  # holdings change; their detail is fetched again
    return {"imported": len(new), "existing": result.counts["exists"],
            "unknown": result.counts["unknown"]}
