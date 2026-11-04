from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.sources import birthdays

CFG = {"timezone": "Europe/Amsterdam",
       "calendar": {"username": "me@example.com", "app_password": "abcd-efgh-ijkl-mnop"}}
NOW = datetime(2026, 11, 3, 23, 30, tzinfo=UTC)  # 00:30 on 4 November in Amsterdam

PRINCIPAL = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response><d:href>/</d:href>
<d:propstat><d:prop><d:current-user-principal><d:href>/123/principal/</d:href>
</d:current-user-principal></d:prop></d:propstat></d:response></d:multistatus>"""
HOME = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"
 xmlns:card="urn:ietf:params:xml:ns:carddav"><d:response><d:href>/123/principal/</d:href>
<d:propstat><d:prop><card:addressbook-home-set>
<d:href>https://p42-contacts.icloud.com/123/carddavhome/</d:href>
</card:addressbook-home-set></d:prop></d:propstat></d:response></d:multistatus>"""
BOOKS = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"
 xmlns:card="urn:ietf:params:xml:ns:carddav">
<d:response><d:href>/123/carddavhome/</d:href><d:propstat><d:prop>
 <d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
<d:response><d:href>/123/carddavhome/card/</d:href><d:propstat><d:prop>
 <d:resourcetype><d:collection/><card:addressbook/></d:resourcetype></d:prop></d:propstat>
</d:response></d:multistatus>"""
CARDS = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
<d:response><d:href>/123/carddavhome/card/</d:href></d:response>
<d:response><d:href>/123/carddavhome/card/a.vcf</d:href></d:response>
<d:response><d:href>/123/carddavhome/card/b.vcf</d:href></d:response>
<d:response><d:href>/123/carddavhome/card/c.vcf</d:href></d:response>
</d:multistatus>"""

ANNA = ("BEGIN:VCARD\r\nVERSION:3.0\r\nN:de Vries;Anna;;;\r\nFN:Anna de Vries\r\n"
        "BDAY:1992-11-04\r\nEND:VCARD")
# Apple's birthday without a year, a group prefix, and a name folded over two lines.
BRAM = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Bram van\r\n  Dijk\r\n"
        "item1.BDAY;X-APPLE-OMIT-YEAR=1604:1604-11-10\r\nEND:VCARD")
NOBODY = "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Plumber\r\nTEL:0612345678\r\nEND:VCARD"


def multiget(*cards: str) -> str:
    found = "".join(f"<d:response><d:href>/x.vcf</d:href><d:propstat><d:prop>"
                    f"<card:address-data>{c}</card:address-data></d:prop></d:propstat></d:response>"
                    for c in cards)
    return (f'<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
            f'xmlns:card="urn:ietf:params:xml:ns:carddav">{found}</d:multistatus>')


class Cloud:
    def __init__(self, login_ok: bool = True) -> None:
        self.login_ok = login_ok
        self.asked: list[str] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            if not self.login_ok:
                return httpx.Response(401)
            path, method = request.url.path, request.method
            if method == "PROPFIND" and path == "/":
                return httpx.Response(207, text=PRINCIPAL)
            if method == "PROPFIND" and path == "/123/principal/":
                return httpx.Response(207, text=HOME)
            if method == "PROPFIND" and path == "/123/carddavhome/":
                return httpx.Response(207, text=BOOKS)
            if method == "PROPFIND" and path == "/123/carddavhome/card/":
                assert request.url.host == "p42-contacts.icloud.com"
                return httpx.Response(207, text=CARDS)
            if method == "REPORT":
                self.asked.append(request.content.decode())
                return httpx.Response(207, text=multiget(ANNA, BRAM, NOBODY, ANNA))
            return httpx.Response(404)
        return httpx.MockTransport(handler)


def collect(cloud: Cloud, store) -> birthdays.People:
    return asyncio.run(birthdays.collect(CFG, store, NOW, transport=cloud.transport()))


def test_birthdays_are_read_from_every_card_in_the_address_book(store):
    cloud = Cloud()
    people = collect(cloud, store).people

    assert [(p.name, p.month, p.day, p.year) for p in people] == [
        ("Anna de Vries", 11, 4, 1992), ("Bram van Dijk", 11, 10, None)]  # Anna once
    [report] = cloud.asked
    assert "addressbook-multiget" in report and report.count("<d:href>") == 3


def test_a_refused_login_raises_so_the_last_list_stays(store):
    with pytest.raises(httpx.HTTPStatusError):
        collect(Cloud(login_ok=False), store)


@pytest.mark.parametrize(("bday", "expected"), [
    ("BDAY:1990-05-12", (1990, 5, 12)),
    ("BDAY;VALUE=date:19900512", (1990, 5, 12)),
    ("BDAY:--0512", (None, 5, 12)),
    ("BDAY:--05-12", (None, 5, 12)),
    ("BDAY:1604-05-12", (None, 5, 12)),
    ("BDAY:1990-05-12T00:00:00Z", (1990, 5, 12)),
    ("BDAY:yesterday", None),
    ("BDAY:1990-13-12", None),
])
def test_the_birthday_forms_in_use(bday, expected):
    person = birthdays.parse_card(f"BEGIN:VCARD\nFN:Sam\n{bday}\nEND:VCARD")
    assert (None if person is None else (person.year, person.month, person.day)) == expected


def test_a_card_without_a_full_name_uses_its_given_and_family_name():
    person = birthdays.parse_card("BEGIN:VCARD\nN:Jansen;Kees;;;\nBDAY:2001-01-02\nEND:VCARD")
    assert person is not None and person.name == "Kees Jansen"
    assert birthdays.parse_card("BEGIN:VCARD\nBDAY:2001-01-02\nEND:VCARD") is None


def payload(*people: dict) -> dict:
    return {"as_of": NOW.isoformat(), "stale": False, "people": list(people)}


def test_the_week_ahead_counts_from_today_and_turns_over_the_year():
    week = birthdays.upcoming(payload(
        {"name": "Anna", "month": 11, "day": 4, "year": 1992},
        {"name": "Bram", "month": 11, "day": 11, "year": None},
        {"name": "Cas", "month": 11, "day": 12, "year": 2000},  # 8 days on: left out
        {"name": "Dirk", "month": 11, "day": 3, "year": 1980},  # yesterday: next year
    ), date(2026, 11, 4))
    assert [(b.name, b.date, b.days, b.turns) for b in week.birthdays] == [
        ("Anna", "2026-11-04", 0, 34), ("Bram", "2026-11-11", 7, None)]

    new_year = birthdays.upcoming(payload({"name": "Eva", "month": 1, "day": 2, "year": 1999}),
                                  date(2026, 12, 30))
    assert [(b.date, b.days, b.turns) for b in new_year.birthdays] == [("2027-01-02", 3, 28)]


def test_the_29th_of_february_counts_as_the_28th_in_other_years():
    week = birthdays.upcoming(payload({"name": "Fem", "month": 2, "day": 29, "year": 2000}),
                              date(2027, 2, 25))
    assert [(b.date, b.turns) for b in week.birthdays] == [("2027-02-28", 27)]


def test_the_api_works_out_today_in_the_hubs_zone(store):
    main.app.state.store = store
    main.app.state.config = CFG
    client = TestClient(main.app)
    assert client.get("/api/birthdays").status_code == 503

    store.put_cache(birthdays.CACHE_KEY, collect(Cloud(), store).model_dump(mode="json"))
    answer = birthdays.serve(CFG, store, NOW)
    assert answer is not None and answer.today == "2026-11-04"  # past midnight in Amsterdam
    assert [(b.name, b.days) for b in answer.birthdays] == [
        ("Anna de Vries", 0), ("Bram van Dijk", 6)]
    body = client.get("/api/birthdays").json()
    assert set(body) == {"as_of", "stale", "today", "birthdays"}
