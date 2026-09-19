#!/usr/bin/env python3
"""Convert a DEGIRO "Transacties" export into a Ghostfolio import file.

    python3 tools/degiro_to_ghostfolio.py ~/Downloads/Transactions.csv > import.json

Ghostfolio's importer wants a ticker plus a data source; DEGIRO exports ISINs,
so the mapping below is explicit rather than guessed. Anything unmapped is
reported on stderr and left out, so a missing entry is never silent.

DEGIRO quirks this handles:
  * Dutch formatting — DD-MM-YYYY dates and comma decimals.
  * Sign convention — a negative Aantal is a SELL.
  * Fees are always in EUR even when the trade is in USD, so they are converted
    with the row's own Wisselkoers rather than a rate looked up later.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime

# Currently held — each one cross-checked against Portfolio.csv and the
# stock-bot position list, which agree on all eleven.
HELD = {
    "US8740391003": "TSM",
    "US0231351067": "AMZN",
    "US0378331005": "AAPL",
    "NL0010273215": "ASML.AS",
    "NL0011821202": "INGA.AS",
    "IE000Q9W2IR3": "AIAA.DE",
    "US6092071058": "MDLZ",
    "US67066G1040": "NVDA",
    "US79466L3024": "CRM",
    "IE00B3XXRP09": "VUSA.AS",
    "IE00BM67HT60": "XDWT.DE",
}

# Closed positions. Needed only so realised gains land in all-time performance.
# Every ticker here was checked against Ghostfolio's own /symbol/lookup rather
# than assumed — Yahoo's public API rejects automated probes, so it cannot be
# used to verify tickers.
CLOSED = {
    "NL0000009082": "KPN.AS",
    "US70450Y1038": "PYPL",
    "NL0011540547": "ABN.AS",
    "NL0011794037": "AD.AS",
    "NL0012817175": "ALFEN.AS",
    "US75734B1008": "RDDT",
    "US88160R1014": "TSLA",
    # Unresolvable, deliberately excluded. Both are fully closed, so the only
    # loss is EUR -37.00 of realised P&L out of all-time performance.
    #   TKWY.AS  Just Eat Takeaway — taken over by Prosus and delisted. Only
    #            JTKWY survives, a USD-quoted ADR; pairing its price history
    #            with these EUR trades would distort the valuation.
    #   VanEck Ethereum ETN — no ticker on the data source at all.
    "NL0012015705": "",
    "DE000A3GPSP7": "",
}

ISIN_TO_TICKER = {**HELD, **CLOSED}


def num(value: str) -> float:
    """DEGIRO writes 1.234,56 — thousands dots, decimal comma."""
    value = value.strip()
    return float(value.replace(".", "").replace(",", ".")) if value else 0.0


def convert(path: str, include_closed: bool = True) -> list[dict]:
    activities: list[dict] = []
    skipped: dict[str, int] = {}

    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) < 15 or row[0] == "Datum" or not row[3].strip():
                continue

            isin = row[3].strip()
            ticker = ISIN_TO_TICKER.get(isin)
            if not ticker or (not include_closed and isin in CLOSED):
                skipped[f"{row[2][:38]} ({isin})"] = skipped.get(isin, 0) + 1
                continue

            quantity = num(row[6])
            if quantity == 0:
                continue

            currency = row[8].strip() or "EUR"
            rate = num(row[12]) or 1.0          # EUR -> trade currency
            fee_eur = abs(num(row[14]))
            fee = fee_eur if currency == "EUR" else fee_eur * rate

            stamp = datetime.strptime(f"{row[0]} {row[1]}", "%d-%m-%Y %H:%M")

            activities.append({
                "currency": currency,
                "dataSource": "YAHOO",
                "date": stamp.isoformat() + ".000Z",
                "fee": round(fee, 2),
                "quantity": abs(quantity),
                "symbol": ticker,
                "type": "BUY" if quantity > 0 else "SELL",
                "unitPrice": num(row[7]),
            })

    for name, count in skipped.items():
        print(f"skipped {count}x {name}", file=sys.stderr)

    activities.sort(key=lambda a: a["date"])
    return activities


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    include_closed = "--held-only" not in sys.argv
    activities = convert(sys.argv[1], include_closed)
    print(f"{len(activities)} activities", file=sys.stderr)
    json.dump({"activities": activities}, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
