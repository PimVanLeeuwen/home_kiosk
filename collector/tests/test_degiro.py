from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.portfolio import degiro, degiro_import, holding

FIXTURES = Path(__file__).parent / "fixtures"
# Shaped like DEGIRO's Transactions export; the English one starts with a BOM.
ENGLISH = (FIXTURES / "degiro_transactions_en.csv").read_text(encoding="utf-8")
DUTCH = (FIXTURES / "degiro_transactions_nl.csv").read_text(encoding="utf-8")

CFG = {"ghostfolio": {"base_url": "http://gf.lan:3333", "security_token": "token"}}


# --- parsing ------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [ENGLISH, DUTCH])
def test_parse_reads_english_and_dutch_exports(text):
    trades, _ = degiro.parse(text)
    nvda, asml = trades[:2]
    assert (nvda.isin, nvda.type, nvda.quantity, nvda.price, nvda.currency) == (
        "US67066G1040", "SELL", 5, 104.98, "USD")
    # Fees in euros, turned into dollars at DEGIRO's rate: (1,19 + 2,00) x 1,1025.
    assert nvda.fee == 3.517
    assert nvda.when.isoformat() == "2024-09-09T15:35:00+02:00"
    assert (asml.type, asml.price, asml.fee, asml.order_id) == ("BUY", 1597.0, 3.0, "ord-2")


def test_parse_joins_wrapped_product_names():
    trades, skipped = degiro.parse(DUTCH)
    assert trades[-1].product == "TAIWAN SEMICONDUCTOR MANUFACTURING CO"
    assert skipped == []


def test_parse_skips_rows_that_are_not_trades():
    trades, skipped = degiro.parse(ENGLISH)
    assert len(trades) == 3
    assert skipped == ["Line 5: not a trade (no product)."]


def test_parse_explains_a_wrong_file():
    with pytest.raises(degiro.ExportError, match="no column for isin, quantity"):
        degiro.parse("Datum,Omschrijving,Mutatie\n01-10-2026,Deposit,100\n")
    with pytest.raises(degiro.ExportError, match="empty"):
        degiro.parse("")


def test_parse_semicolon_files_and_derived_rates():
    text = (
        "Date;Time;Product;ISIN;Quantity;Price;;Local value;;Value EUR;"
        "Transaction and/or third party fees EUR;Order ID\n"
        "01-10-2026;10:00;APPLE INC;US0378331005;2;200.00;USD;-400.00;USD;-363.64;-1.00;o\n"
    )
    (trade,), _ = degiro.parse(text)
    # No rate column: 400 / 363,64 dollars per euro.
    assert trade.fee == round(400 / 363.64, 4)


def test_header_keys_keep_words_that_are_not_currencies():
    assert degiro._header_key("Value EUR") == "value"
    assert degiro._header_key("AutoFX Fee") == "autofx fee"
    assert degiro._header_key("﻿Date") == "date"


# --- preview and import ---------------------------------------------------------------------


EXISTING = [
    # The NVDA sale, already imported earlier (at midnight UTC, without an order ID).
    {"accountId": "acc-degiro", "date": "2024-09-09T00:00:00.000Z", "type": "SELL", "quantity": 5,
     "unitPrice": 104.98, "assetProfile": {"symbol": "NVDA", "dataSource": "YAHOO",
                                           "name": "NVIDIA Corporation"}},
    {"accountId": "acc-degiro", "date": "2024-03-01T00:00:00.000Z", "type": "BUY", "quantity": 1,
     "unitPrice": 600.0, "assetProfile": {"symbol": "ASML.AS", "dataSource": "YAHOO",
                                          "name": "ASML Holding N.V."}},
    {"accountId": "acc-degiro", "date": "2024-03-01T00:00:00.000Z", "type": "BUY", "quantity": 3,
     "unitPrice": 60.0, "assetProfile": {"symbol": "XDWT.DE", "dataSource": "YAHOO",
                                         "name": "Xtrackers MSCI World IT"}},
]
def item(symbol: str, currency: str) -> dict:
    return {"symbol": symbol, "dataSource": "YAHOO", "name": symbol, "currency": currency}


LOOKUP = {
    "US67066G1040": [item("NVDA", "USD")],
    "NL0010273215": [item("ASML.AS", "EUR"), item("ASML", "USD")],
    # Yahoo finds another listing than the one held: the hub has to ask.
    "IE00BM67HT60": [item("XDWT.L", "GBP")],
}


class FakeGhostfolio:
    def __init__(self):
        self.imported: list[dict] = []
        self.lookups: list[str] = []
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        if path == "/api/v1/auth/anonymous":
            return httpx.Response(200, json={"authToken": "jwt"})
        if path == "/api/v1/activities":
            return httpx.Response(200, json={"activities": EXISTING + self.imported, "count": 3})
        if path == "/api/v1/account":
            return httpx.Response(200, json={"accounts": [
                {"id": "acc-other", "name": "Savings"},
                {"id": "acc-degiro", "name": "Broker", "platform": {"name": "DEGIRO"}}]})
        if path == "/api/v1/symbol/lookup":
            query = request.url.params["query"]
            self.lookups.append(query)
            return httpx.Response(200, json={"items": LOOKUP.get(query, [])})
        if path == "/api/v1/import":
            if self.status != 200:
                message = ["activities.0.symbol is not valid"]
                return httpx.Response(self.status, json={"message": message})
            body = json.loads(request.content)["activities"]
            # Stored the way Ghostfolio lists them afterwards.
            self.imported += [
                {**a, "assetProfile": {"symbol": a["symbol"], "dataSource": a["dataSource"],
                                       "name": a["symbol"]}}
                for a in body
            ]
            return httpx.Response(201, json={"activities": body})
        return httpx.Response(404)


@pytest.fixture
def fake():
    holding._clients.clear()
    return FakeGhostfolio()


@pytest.fixture
def degiro_store(store):
    degiro_import.ensure_tables(store)
    return store


def preview(store, fake, text=ENGLISH, choices=None):
    return asyncio.run(degiro_import.preview(CFG, store, text, choices, httpx.MockTransport(fake)))


def test_preview_sorts_rows_into_new_existing_and_unknown(degiro_store, fake):
    result = preview(degiro_store, fake)

    assert [(r.symbol, r.status) for r in result.rows] == [
        ("NVDA", "exists"), ("ASML.AS", "new"), (None, "unknown")]
    assert result.counts == {"new": 1, "exists": 1, "unknown": 1, "ignored": 0}
    assert result.account_id == "acc-degiro"
    (product,) = result.unknown
    assert product.isin == "IE00BM67HT60"
    # Your holdings first, the closest name marked; Yahoo's other listing last.
    assert [(c.symbol, c.held, c.suggested) for c in product.candidates] == [
        ("XDWT.DE", True, True), ("ASML.AS", True, False), ("NVDA", True, False),
        ("XDWT.L", False, False)]
    assert product.candidates[0].name == "Xtrackers MSCI World IT"


def test_an_existing_activity_counts_once(degiro_store, fake):
    twice = ENGLISH.splitlines()[:2] + [ENGLISH.splitlines()[1].replace("ord-1", "ord-9")]
    result = preview(degiro_store, fake, "\n".join(twice) + "\n")
    assert [r.status for r in result.rows] == ["exists", "new"]


def test_import_adds_only_new_rows_and_remembers_choices(degiro_store, fake):
    choices = {"IE00BM67HT60": degiro_import.Choice(data_source="YAHOO", symbol="XDWT.DE")}
    result = asyncio.run(degiro_import.run_import(
        CFG, degiro_store, ENGLISH, "acc-degiro", choices, httpx.MockTransport(fake)))

    assert result == {"imported": 2, "existing": 1, "unknown": 0, "ignored": 0}
    assert [(a["symbol"], a["type"], a["quantity"]) for a in fake.imported] == [
        ("ASML.AS", "BUY", 1), ("XDWT.DE", "BUY", 2)]
    asml = {k: v for k, v in fake.imported[0].items() if k != "assetProfile"}
    assert asml == {
        "accountId": "acc-degiro", "comment": "DEGIRO order ord-2", "currency": "EUR",
        "dataSource": "YAHOO", "date": "2026-10-02T07:05:00Z", "fee": 3.0, "quantity": 1.0,
        "symbol": "ASML.AS", "type": "BUY", "unitPrice": 1597.0,
    }

    # The same file again adds nothing, and the ETF no longer needs a choice.
    fake.lookups.clear()
    again = preview(degiro_store, fake)
    assert again.counts == {"new": 0, "exists": 3, "unknown": 0, "ignored": 0}
    assert "IE00BM67HT60" not in fake.lookups


def test_a_product_can_be_left_out_for_good(degiro_store, fake):
    leave_out = {"IE00BM67HT60": degiro_import.Choice(ignore=True)}
    result = asyncio.run(degiro_import.run_import(
        CFG, degiro_store, ENGLISH, "acc-degiro", leave_out, httpx.MockTransport(fake)))
    assert result == {"imported": 1, "existing": 1, "unknown": 0, "ignored": 1}
    assert [a["symbol"] for a in fake.imported] == ["ASML.AS"]

    fake.lookups.clear()
    again = preview(degiro_store, fake)
    assert again.counts == {"new": 0, "exists": 2, "unknown": 0, "ignored": 1}
    assert again.unknown == [] and "IE00BM67HT60" not in fake.lookups
    assert again.rows[-1].status == "ignored" and again.rows[-1].symbol is None


def test_a_weak_name_match_is_not_suggested():
    held = {("YAHOO", "AIAA.DE")}
    names = {("YAHOO", "AIAA.DE"): "iShares AI Adopters & Applications UCITS ETF"}
    (offer,) = degiro_import._offer("VANGUARD S&P 500 UCITS ETF USD DIS", [], held, names)
    assert offer.suggested is False


def test_older_tables_get_the_ignored_column(store):
    with store.connect() as conn:
        conn.execute("CREATE TABLE degiro_symbol (isin TEXT PRIMARY KEY, "
                     "data_source TEXT NOT NULL, symbol TEXT NOT NULL, chosen_at TEXT NOT NULL)")
        conn.execute("INSERT INTO degiro_symbol VALUES ('IE00BM67HT60', 'YAHOO', 'XDWT.DE', 'x')")
    degiro_import.ensure_tables(store)
    assert degiro_import.saved_choices(store)["IE00BM67HT60"].ignore is False


def test_import_refuses_an_unknown_account_and_bad_symbols(degiro_store, fake):
    with pytest.raises(degiro_import.DegiroError, match="account"):
        asyncio.run(degiro_import.run_import(CFG, degiro_store, ENGLISH, "nope", {},
                                             httpx.MockTransport(fake)))
    bad = {"IE00BM67HT60": degiro_import.Choice(data_source="YAHOO", symbol="../x")}
    with pytest.raises(degiro_import.DegiroError, match="not a valid symbol"):
        asyncio.run(degiro_import.run_import(CFG, degiro_store, ENGLISH, "acc-degiro", bad,
                                             httpx.MockTransport(fake)))
    assert fake.imported == []


# --- endpoints -------------------------------------------------------------------------------


@pytest.fixture
def client(degiro_store, fake):
    main.app.state.store = degiro_store
    main.app.state.config = CFG
    main.app.state.ghostfolio_transport = httpx.MockTransport(fake)
    yield TestClient(main.app, headers={"origin": "http://testserver"})
    del main.app.state.ghostfolio_transport


def test_preview_and_import_endpoints(client, fake):
    body = client.post("/api/portfolio/degiro/preview", json={"csv": ENGLISH}).json()
    assert body["counts"] == {"new": 1, "exists": 1, "unknown": 1, "ignored": 0}

    resp = client.post("/api/portfolio/degiro/import", json={
        "csv": ENGLISH, "account_id": "acc-degiro",
        "choices": {"IE00BM67HT60": {"data_source": "YAHOO", "symbol": "XDWT.DE"}}})
    assert resp.json() == {"imported": 2, "existing": 1, "unknown": 0, "ignored": 0}


def test_remembered_choices_can_be_listed_and_forgotten(client, degiro_store):
    degiro_import.save_choices(degiro_store, {
        "IE00BM67HT60": degiro_import.Choice(data_source="YAHOO", symbol="XDWT.L")})
    assert client.get("/api/portfolio/degiro/choices").json() == {
        "IE00BM67HT60": {"data_source": "YAHOO", "symbol": "XDWT.L", "ignore": False}}

    assert client.delete("/api/portfolio/degiro/choices/IE00BM67HT60").json() == {}
    assert client.delete("/api/portfolio/degiro/choices/IE00BM67HT60").status_code == 404
    # Asked about again on the next preview.
    body = client.post("/api/portfolio/degiro/preview", json={"csv": ENGLISH}).json()
    assert [u["isin"] for u in body["unknown"]] == ["IE00BM67HT60"]


def test_endpoints_explain_problems(client, fake):
    wrong = client.post("/api/portfolio/degiro/preview", json={"csv": "a,b\n1,2\n"})
    assert wrong.status_code == 422 and "DEGIRO Transactions export" in wrong.json()["detail"]

    fake.status = 400
    refused = client.post("/api/portfolio/degiro/import", json={
        "csv": ENGLISH, "account_id": "acc-degiro",
        "choices": {"IE00BM67HT60": {"data_source": "YAHOO", "symbol": "XDWT.DE"}}})
    assert refused.status_code == 502
    assert refused.json()["detail"] == "Ghostfolio refused: activities.0.symbol is not valid"


def test_import_needs_the_same_origin(client):
    other = TestClient(main.app, headers={"origin": "https://evil.example"})
    resp = other.post("/api/portfolio/degiro/import", json={"csv": ENGLISH, "account_id": "x"})
    assert resp.status_code == 403
