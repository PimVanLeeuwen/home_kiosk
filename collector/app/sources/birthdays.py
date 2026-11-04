"""Birthdays (plan.md M32): the birthday field of the owner's iCloud contacts, for the
Birthdays card on Home and the Door panel.

iCloud's Birthdays calendar is made from Contacts on the devices and is not served over
CalDAV, so this reads the contacts themselves over CardDAV (`contacts.icloud.com`), with
the same Apple ID and app-specific password as the calendar (app/sources/agenda.py),
read-only. Every address book is listed with its cards' addresses (PROPFIND), then the
cards are fetched in batches (addressbook-multiget), which every CardDAV server answers.

Only a name and a date leave each card; the hub keeps them all and works out which fall
in the coming week when asked (`upcoming`), so midnight turns over on time although the
contacts are read every 6 hours. Names are personal data: served to the hub and the
panels, never logged.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from ..models import Envelope
from ..store import Store
from . import agenda

CACHE_KEY = "birthdays"
SERVER = "https://contacts.icloud.com"
AHEAD = 7  # days after today
BATCH = 100  # cards per multiget
NS = {"d": "DAV:", "card": "urn:ietf:params:xml:ns:carddav"}
# Apple writes a birthday without a year as 1604 (with X-APPLE-OMIT-YEAR=1604).
OMIT_YEAR = 1604

HOME = ('<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav"><d:prop>'
        '<card:addressbook-home-set/></d:prop></d:propfind>')
BOOKS = '<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'
CARDS = '<d:propfind xmlns:d="DAV:"><d:prop><d:getetag/></d:prop></d:propfind>'


class Person(BaseModel):
    name: str
    month: int
    day: int
    year: int | None = None  # None when the card has no birth year


class People(Envelope):
    people: list[Person]


class Birthday(BaseModel):
    name: str
    date: str  # this year's (or next year's) birthday, YYYY-MM-DD
    days: int  # 0 today, 1 tomorrow, ...
    turns: int | None = None  # the age they turn, when the year is known


class Upcoming(Envelope):
    today: str
    birthdays: list[Birthday]  # nearest first, then by name


def settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """The calendar's iCloud login; on when the calendar is."""
    cal = agenda.settings(cfg)
    server = ((cfg.get("calendar") or {}).get("contacts_server") or SERVER).rstrip("/")
    return {"enabled": cal["enabled"], "auth": cal["auth"], "server": server,
            "timezone": cal["timezone"]}


# --- vCards ---------------------------------------------------------------------------


def _unfold(card: str) -> list[str]:
    """The card's lines with folded ones joined (a line starting with a space or tab
    continues the one before)."""
    return re.sub(r"\r?\n[ \t]", "", card).splitlines()


def _value(text: str) -> str:
    return (text.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",")
            .replace("\\;", ";").replace("\\\\", "\\")).strip()


def _birthday(params: str, value: str) -> tuple[int | None, int, int] | None:
    """(year or None, month, day) from a BDAY: 1990-05-12, 19900512, --0512, --05-12,
    or Apple's 1604-05-12 for a day without a year; a time after it is ignored."""
    value = value.strip().split("T", 1)[0]
    m = (re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", value)
         or re.fullmatch(r"--()(\d{2})-?(\d{2})", value))
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else None
    month, day = int(m.group(2)), int(m.group(3))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    if year == OMIT_YEAR or "X-APPLE-OMIT-YEAR" in params.upper():
        year = None
    return year, month, day


def parse_card(card: str) -> Person | None:
    """The name and birthday on one vCard; None without a birthday or a name."""
    name = given = family = ""
    found = None
    for line in _unfold(card):
        key, sep, value = line.partition(":")
        if not sep:
            continue
        prop, _, params = key.partition(";")
        prop = prop.rsplit(".", 1)[-1].upper()  # "item1.BDAY": Apple's groups
        if prop == "FN":
            name = _value(value)
        elif prop == "N":
            parts = value.split(";")
            family, given = _value(parts[0]), _value(parts[1]) if len(parts) > 1 else ""
        elif prop == "BDAY" and found is None:
            found = _birthday(params, value)
    name = name or " ".join(p for p in (given, family) if p)
    if found is None or not name:
        return None
    year, month, day = found
    return Person(name=name, month=month, day=day, year=year)


# --- reading iCloud -------------------------------------------------------------------


def _href(xml: str, element: str) -> str:
    node = ET.fromstring(xml).find(f".//{element}/d:href", NS)
    if node is None or not (node.text or "").strip():
        raise ValueError(f"no {element} in the answer")
    return node.text.strip()


def _hrefs(xml: str, keep: Any) -> list[str]:
    out = []
    for resp in ET.fromstring(xml).iterfind("d:response", NS):
        href = (resp.findtext("d:href", "", NS) or "").strip()
        if href and keep(resp, href):
            out.append(href)
    return out


def _is_book(resp: ET.Element, _href: str) -> bool:
    return resp.find(".//d:resourcetype/card:addressbook", NS) is not None


def _is_card(_resp: ET.Element, href: str) -> bool:
    return href.endswith(".vcf")


def _multiget(hrefs: list[str]) -> str:
    wanted = "".join(f"<d:href>{h}</d:href>" for h in hrefs)
    return ('<card:addressbook-multiget xmlns:d="DAV:" '
            'xmlns:card="urn:ietf:params:xml:ns:carddav"><d:prop><card:address-data/>'
            f'</d:prop>{wanted}</card:addressbook-multiget>')


def parse_cards(xml: str) -> list[Person]:
    return [p for node in ET.fromstring(xml).iterfind(".//card:address-data", NS)
            if node.text and (p := parse_card(node.text)) is not None]


async def read(client: httpx.AsyncClient, server: str) -> list[Person]:
    principal = _href(await agenda._dav(client, "PROPFIND", f"{server}/", "0", agenda.PRINCIPAL),
                      "d:current-user-principal")
    home = _href(await agenda._dav(client, "PROPFIND", f"{server}{principal}", "0", HOME),
                 "card:addressbook-home-set")
    if not home.startswith("http"):
        home = f"{server}{home}"
    base = "{0.scheme}://{0.netloc}".format(urlsplit(home))
    books = _hrefs(await agenda._dav(client, "PROPFIND", home, "1", BOOKS), _is_book)
    people: list[Person] = []
    for book in books:
        url = f"{base}{book}"
        cards = _hrefs(await agenda._dav(client, "PROPFIND", url, "1", CARDS), _is_card)
        for i in range(0, len(cards), BATCH):
            answer = await agenda._dav(client, "REPORT", url, "1", _multiget(cards[i:i + BATCH]))
            people += parse_cards(answer)
    return people


async def collect(cfg: dict[str, Any], store: Store, now: datetime | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> People:
    """Raises when iCloud cannot be read, so the last good list stays cached, flagged
    stale. The same person in two address books counts once."""
    s = settings(cfg)
    now = now or datetime.now(UTC)
    async with httpx.AsyncClient(auth=s["auth"], timeout=agenda.TIMEOUT_SECONDS,
                                 transport=transport) as client:
        people = await read(client, s["server"])
    unique = {(p.name, p.month, p.day): p for p in people}
    return People(as_of=now, stale=False,
                  people=sorted(unique.values(), key=lambda p: (p.month, p.day, p.name)))


# --- the week ahead -------------------------------------------------------------------


def _on(person: Person, year: int) -> date:
    """The birthday in `year`; 29 February counts as the 28th in other years."""
    try:
        return date(year, person.month, person.day)
    except ValueError:
        return date(year, person.month, 28)


def upcoming(payload: dict[str, Any], today: date, ahead: int = AHEAD) -> Upcoming:
    """The birthdays from today to `ahead` days on, nearest first."""
    found = []
    for raw in payload.get("people") or []:
        person = Person(**raw)
        day = _on(person, today.year)
        if day < today:
            day = _on(person, today.year + 1)
        days = (day - today).days
        if days > ahead:
            continue
        turns = day.year - person.year if person.year else None
        found.append(Birthday(name=person.name, date=day.isoformat(), days=days,
                              turns=turns if turns and turns > 0 else None))
    found.sort(key=lambda b: (b.days, b.name))
    return Upcoming(as_of=payload["as_of"], stale=bool(payload.get("stale")),
                    today=today.isoformat(), birthdays=found)


def serve(cfg: dict[str, Any], store: Store, now: datetime | None = None) -> Upcoming | None:
    """This week's birthdays from the cached contacts; None before the first read."""
    payload = store.get_cache(CACHE_KEY)
    if payload is None:
        return None
    zone = agenda.settings(cfg)["timezone"]
    return upcoming(payload, (now or datetime.now(UTC)).astimezone(zone).date())
