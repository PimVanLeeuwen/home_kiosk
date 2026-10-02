"""Read a DEGIRO Transactions export (CSV), in English or Dutch.

Columns are found by their header name, not their position, so a renamed or
moved column is a one-line change to NAMES. DEGIRO leaves the currency columns
unnamed: each sits right after the amount it belongs to ("Price", then the
price's currency).

    Date,Time,Product,ISIN,Reference exchange,Venue,Quantity,Price,,Local value,,
    Value EUR,Exchange rate,AutoFX Fee,Transaction and/or third party fees EUR,
    Total EUR,Order ID
    Datum,Tijd,Product,ISIN,Beurs,Uitvoeringsplaats,Aantal,Koers,,Lokale waarde,,
    Waarde EUR,Wisselkoers,AutoFX Kosten,Transactiekosten en/of kosten van derden EUR,
    Totaal EUR,Order ID

Numbers follow the export's language: "1,208.88" in English, "1.208,88" in Dutch.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
MAX_BYTES = 2_000_000

# Field -> header names (lower case, before any trailing currency code).
NAMES: dict[str, tuple[str, ...]] = {
    "date": ("date", "datum"),
    "time": ("time", "tijd"),
    "product": ("product",),
    "isin": ("isin",),
    "exchange": ("reference exchange", "beurs"),
    "quantity": ("quantity", "aantal"),
    "price": ("price", "koers"),
    "local_value": ("local value", "lokale waarde"),
    "value": ("value", "waarde"),
    "rate": ("exchange rate", "wisselkoers"),
    "autofx": ("autofx fee", "autofx kosten"),
    "fees": ("transaction and/or third party fees", "transaction costs",
             "transactiekosten en/of kosten van derden", "transactiekosten"),
    "order_id": ("order id", "order-id"),
}
REQUIRED = ("date", "isin", "quantity", "price")
DUTCH = {"datum", "aantal", "koers"}
CURRENCY = re.compile(r"^[A-Z]{3}$")


class ExportError(ValueError):
    """The file is not a DEGIRO Transactions export; the message says why."""


@dataclass
class Trade:
    line: int  # in the file, for the preview
    when: datetime  # Amsterdam time
    product: str
    isin: str
    exchange: str
    type: str  # BUY or SELL
    quantity: float  # always positive
    price: float
    currency: str  # of the price
    fee: float  # in `currency`
    order_id: str

    @property
    def day(self) -> date:
        return self.when.date()


def _header_key(name: str) -> str:
    """'Value EUR' -> 'value'. Only an upper-case currency code goes, so
    'AutoFX Fee' stays 'autofx fee'."""
    return re.sub(r"\s+[A-Z]{3}$", "", name.strip().lstrip("\ufeff")).lower()


def _columns(header: list[str]) -> dict[str, int]:
    keys = [_header_key(h) for h in header]
    found: dict[str, int] = {}
    for field, names in NAMES.items():
        for i, key in enumerate(keys):
            if key in names:
                found[field] = i
                break
    missing = [f for f in REQUIRED if f not in found]
    if missing:
        raise ExportError(
            "This does not look like a DEGIRO Transactions export: no column for "
            + ", ".join(missing) + ". Export it from DEGIRO under Inbox > Transactions.")
    return found


def number(text: str, dutch: bool) -> float | None:
    text = text.strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    text = text.replace(".", "").replace(",", ".") if dutch else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _currency_after(row: list[str], index: int | None) -> str | None:
    if index is None or index + 1 >= len(row):
        return None
    value = row[index + 1].strip().upper()
    return value if CURRENCY.match(value) else None


def _when(day: str, at: str) -> datetime:
    parsed = datetime.strptime(day.strip(), "%d-%m-%Y").date()
    clock = datetime.strptime(at.strip(), "%H:%M").time() if at.strip() else time(12, 0)
    return datetime.combine(parsed, clock, AMSTERDAM)


def parse(text: str) -> tuple[list[Trade], list[str]]:
    """The trades, and a sentence per row that was left out."""
    if len(text.encode()) > MAX_BYTES:
        raise ExportError("The file is too large for a transactions export.")
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        raise ExportError("The file is empty.")
    columns = _columns(rows[0])
    dutch = bool(DUTCH & {_header_key(h) for h in rows[0]})

    trades: list[Trade] = []
    skipped: list[str] = []
    for line, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(field: str, row: list[str] = row) -> str:
            i = columns.get(field)
            return row[i].strip() if i is not None and i < len(row) else ""

        isin = cell("isin").upper()
        quantity = number(cell("quantity"), dutch)
        price = number(cell("price"), dutch)
        currency = (_currency_after(row, columns.get("price"))
                    or _currency_after(row, columns.get("local_value")))
        if not isin or not quantity or price is None or not currency:
            skipped.append(f"Line {line}: not a trade ({cell('product') or 'no product'}).")
            continue
        try:
            when = _when(cell("date"), cell("time"))
        except ValueError:
            skipped.append(f"Line {line}: unreadable date “{cell('date')}”.")
            continue

        # Fees are booked in euros (negative); the activity needs them in the
        # price's currency. DEGIRO's rate is units of that currency per euro.
        fee_eur = abs(number(cell("fees"), dutch) or 0) + abs(number(cell("autofx"), dutch) or 0)
        rate = number(cell("rate"), dutch)
        if currency == "EUR":
            rate = 1.0
        elif not rate:
            local = number(cell("local_value"), dutch)
            value = number(cell("value"), dutch)
            rate = abs(local / value) if local and value else 1.0
        trades.append(Trade(
            line=line, when=when, product=cell("product"), isin=isin,
            exchange=cell("exchange"), type="BUY" if quantity > 0 else "SELL",
            quantity=abs(quantity), price=price, currency=currency,
            fee=round(fee_eur * rate, 4), order_id=cell("order_id"),
        ))
    return trades, skipped
