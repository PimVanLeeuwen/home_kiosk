# Desk Dashboard — Build Spec

A 7" portrait screen on a desk that rotates through four dashboard views:
portfolio overview, single-holding spotlight, news headlines, NAS statistics.

Approved visual design lives on a canvas — copy the artboard markup as the
starting point for each view rather than rebuilding from this description:
https://claude.ai/artifact/4T9cYJPuaWamJic3aBfspz

---

## 1. Decisions already made

| Decision | Choice |
|---|---|
| Visual direction | "Modern" — dark, Instrument Sans + JetBrains Mono, card-based |
| Orientation | Portrait, 720 × 1280, native (no rotation config) |
| Portfolio data | Ghostfolio, self-hosted |
| Collector language | Python |
| Rotation | Fixed equal loop, all four views, equal duration |
| Where it runs | Everything on the Ugreen NAS; the Pi is a dumb kiosk |
| Network | LAN-only. Nothing exposed to the internet. |
| Metrics backend | SQLite in the collector. No Prometheus. |

## 2. Still to fill in

These block specific tasks but not the overall build. Marked `TODO(user)` where they appear.

1. **Holdings** — entered into Ghostfolio by the user, not by this project.
2. **Broker CSV export** — used for the initial Ghostfolio import.
3. **Night behaviour** — dim / off / always on, and at what times.
4. **Hardware owned?** — if not, see shopping list in §3.

### Resolved

| Was open | Answer |
|---|---|
| Ugreen model | **DXP4800 Plus**, Intel Pentium Gold 8505 → `linux/amd64` images. 5 SATA disks visible to Scrutiny, 2 NVMe. Four btrfs pools `/volume1`–`/volume4`. |
| RAID level | `md1`, `md2`, `md4` are single-disk arrays, `md3` has two. Most pools have **no parity** — a failure means restoring from Hetzner. |
| Existing services | Documented in `PimVanLeeuwen/nas-docker`. Taken: 2283, 3000, 3001, 5055, 5984, 6767, 7878, 8080, 8081, 8082, 8085, 8090, 8096, 8888, 8989, 9091, 9696. |
| Dashboard port | **8083** — 8080 is Scrutiny. Collector on 8000, both previously free. |
| RSS feeds | Three groups: Tech, Nederland, Self-hosted / Apple / Linux. See `config.yaml` in §5. |
| Read-later service | **Readeck**, self-hosted on the NAS. See §8. |

---

## 3. Hardware

Verified against Raspberry Pi's own documentation, not from memory — two details
in the original draft were wrong (see the notes).

### Required

| Item | Spec | Why / note |
|---|---|---|
| Raspberry Pi 5 | 4GB | Pi 4 works too, but needs a **different display cable** — see below. Zero series is explicitly incompatible with the display. |
| Raspberry Pi Touch Display 2 | 7", 720 × 1280 | Natively portrait, matches the design 1:1. Ships with the FFC cable, a 3-pin GPIO power cable and 8× M2.5 screws. |
| Official 27W USB-C PSU | 5V / 5A | **Not optional.** The Pi 5 wants 5V/5A; on a 15W supply it caps *all* peripherals at 600mA, and the display draws its power from the GPIO 5V pins. |
| Active Cooler | official, 4-pin JST-SH PWM | This runs 24/7 behind a display. The fan idles below 50°C and ramps to 100% at 75°C. |
| Storage | 32GB A2 microSD, or small USB SSD | SSD preferred for write endurance; pair with `log2ram` either way (§9). |
| Stand or case | **must be Touch Display 2 compatible** | See the compatibility warning below. |

### Display cable — depends on the Pi

The Touch Display 2 ships with the right cable *for the device you specify*, so
say which Pi when ordering:

| Pi | 7" display cable |
|---|---|
| Raspberry Pi 5 | **22-way to 15-way** FFC (Standard–Mini) |
| Pi 4 and earlier | 15-way to 15-way FFC |

The display is powered by the host — no separate PSU — via the included 3-pin
cable from the display's J1 port to 5V and ground on the GPIO header.

### Case compatibility warning

The original draft suggested "SmartiPi", but **SmartiPi Touch 2 fits the
first-generation 7" display (800 × 480), not this one**. Panel size and rear
mounting holes differ. Options that do fit Touch Display 2:

- **SmartiPi Touch Pro 3** — desk stand, explicitly lists 7" Touch Display 2
- **KKSB Display Stand** — metal, adjustable angle, external power button
- **The Pi Hut Panel Mounting Enclosure** — wall/panel mount, 7" only
- **Waveshare PI5-CASE-TD2** — budget enclosure
- 3D print — parametric design on Printables, uses the included M2.5 screws

Avoid anything listing 800 × 480 or the "1st gen" 7" screen.

### Useful but not required

| Item | When you need it |
|---|---|
| microSD card reader | Flashing the card, if the machine has no slot |
| micro-HDMI → HDMI cable | Debugging if the DSI display does not come up at first boot |
| Ethernet cable | Optional; Wi-Fi is fine for a LAN-only dashboard |

Backlight brightness is a writable file under `/sys/class/backlight/` — locate
the exact node at setup time, it varies.

---

## 4. Architecture

```
┌─────────────────────── Ugreen NAS (Docker) ───────────────────────┐
│                                                                    │
│  ghostfolio ──┐                                                    │
│  postgres     │                                                    │
│  redis        │                                                    │
│               ├──► collector (Python) ──► SQLite ──┐               │
│  node_exporter│      :8000  │                      │               │
│  scrutiny ────┘             └──► /api/*.json ──────┤               │
│  (already running)                                 │               │
│  readeck ◄── tap-to-save                           ▼               │
│                                          caddy ──► dashboard/      │
│                                           :8083                    │
└────────────────────────────────────────────────────┬───────────────┘
                                                     │ LAN
                                          ┌──────────▼──────────┐
                                          │ Pi 5 + Touch Display│
                                          │ Chromium --kiosk    │
                                          └─────────────────────┘
```

### Repo layout

```
desk-dashboard/
├── docker-compose.yml
├── .env.example
├── collector/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── config.yaml              # feeds, tickers, refresh intervals
│   └── app/
│       ├── main.py              # FastAPI app, four endpoints
│       ├── scheduler.py         # APScheduler jobs
│       ├── store.py             # SQLite: snapshots + samples
│       ├── models.py            # pydantic response models
│       └── sources/
│           ├── ghostfolio.py
│           ├── prices.py        # Twelve Data primary, yfinance fallback
│           ├── feeds.py         # feedparser
│           └── nas.py           # exporter scraping
├── dashboard/
│   ├── index.html               # carousel shell
│   ├── views/                   # one HTML fragment per view
│   │   ├── portfolio.html
│   │   ├── spotlight.html
│   │   ├── news.html
│   │   └── nas.html
│   ├── fixtures/                # M2 test data, also the schema contract
│   └── assets/
│       ├── tokens.css           # §7 tokens, per-view accent
│       ├── views.css            # component styles from the artboards
│       ├── fonts.css
│       ├── app.js
│       └── fonts/               # self-hosted woff2, see §7
├── .github/workflows/           # ruff lint, then build and push the image
├── caddy/Caddyfile
└── kiosk/                       # Pi-side setup, see §9
    ├── setup.sh
    ├── kiosk.service
    └── brightness.py
```

---

## 5. Collector

Python 3.14, FastAPI + APScheduler, SQLite via plain `sqlite3`.
(`requires-python` stays `>=3.12`; the image and dev venv both run 3.14 so the
runtime is the same everywhere.)
No auth — LAN only, bound to the Docker network.

### Refresh cadences

| Job | Interval |
|---|---|
| Portfolio (Ghostfolio) | 15 min, 08:00–23:00 |
| Spotlight detail (price API) | 15 min, market hours only |
| Feeds | 10 min |
| NAS metrics | 60 s |
| Daily portfolio snapshot | once, 23:10 |

### SQLite tables

- `portfolio_snapshot(date PK, total_value, currency)` — 30+ daily rows for the chart
- `nas_sample(ts PK, rx_bytes, tx_bytes, cpu_pct, ram_pct, cpu_temp)` — 24h rolling, prune beyond
- `storage_sample(date, mountpoint, used_bytes)` — one row per pool per day, for
  the runway projection. `nas_sample`'s 24h window is far too short to fit a
  trend to, so this is a separate table.
- `cache(key PK, payload_json, fetched_at)` — last-good response per endpoint.
  Also holds `nas_counters`, the previous raw CPU and network counters. Rates
  need two readings, and keeping them here means they survive a restart.

### Staleness rule

Every response carries `as_of` and `stale`. If a source fails, serve the cached
payload with `stale: true` and `as_of` unchanged. Never 500 to the frontend —
the screen must always render something.

### Endpoints

**`GET /api/portfolio`**
```json
{
  "as_of": "2026-09-18T21:09:00+02:00",
  "stale": false,
  "currency": "EUR",
  "total_value": 24490.42,
  "change": {
    "day_abs": 220.10, "day_pct": 0.91,
    "month_pct": 2.44, "year_pct": 11.80, "all_pct": 38.20
  },
  "history": [{ "d": "2026-08-19", "v": 22530.00 }],
  "holdings": [
    { "symbol": "ASML", "name": "ASML Holding",
      "value": 1484.20, "day_pct": 4.2, "weight_pct": 6.1 }
  ],
  "allocation": [{ "label": "Equities", "pct": 62 }]
}
```
`holdings` sorted by value descending; the view renders the top 5.
`history` is 30 daily points from `portfolio_snapshot`.

**`GET /api/spotlight`**
```json
{
  "as_of": "2026-09-18T21:09:00+02:00",
  "stale": false,
  "symbol": "ASML", "name": "ASML Holding N.V.", "exchange": "Euronext Amsterdam",
  "price": 742.10, "currency": "EUR", "day_abs": 29.80, "day_pct": 4.2,
  "history": [{ "d": "2025-09-19", "v": 612.40 }],
  "day_range": { "low": 712.00, "high": 744.00 },
  "range_52w": { "low": 498.20, "high": 748.60 },
  "position": {
    "shares": 2, "avg_cost": 610.40, "value": 1484.20,
    "unrealised_abs": 263.40, "unrealised_pct": 21.6,
    "weight_pct": 6.1, "held_since": "2023-03"
  },
  "next_earnings": "2026-10-15"
}
```
**Selection rule: a random holding, re-picked on each 15-minute refresh** —
cash excluded. Not the biggest mover: that tends to be the same name for days at
a time, which makes the view static. The previous pick is stored under
`spotlight_last` so the same holding is never featured twice running.

`history` is ~52 weekly points, taken as every 7th of a year of daily closes.

**Everything in this payload is in the asset's own currency.** Ghostfolio mixes
them — `marketPrice` is native, while `investment`, `valueInBaseCurrency` and
the performance figures are in the portfolio's base currency. Reporting both
under one label turns a EUR amount into a dollar one. The conversion is derived
from the two prices (`marketPrice` ÷ `valueInBaseCurrency/quantity`), needing no
FX lookup. Verified: avg cost comes out at USD 105.40 for TSM, matching DEGIRO's
GAK exactly, and `shares × price` equals market value to the cent.

`day_range` and `next_earnings` are **always omitted** with Ghostfolio as the
source: it stores daily closes, so there is no intraday high/low, and it has no
earnings calendar. The facts row falls back to invested and held-since.
`next_earnings` is optional — omit the field entirely if unavailable, and the
view hides that cell rather than showing a dash.

**`GET /api/news`**
```json
{
  "as_of": "2026-09-18T21:12:00+02:00",
  "stale": false,
  "groups": [
    {
      "id": "tech", "title": "Tech", "new_count": 3,
      "items": [
        { "title": "…", "source": "Reuters",
          "published": "2026-09-18T20:56:00+02:00",
          "age_label": "18 min ago", "url": "https://…", "meta": null }
      ]
    }
  ]
}
```
- Titles truncated **server-side** to 70 characters at a word boundary plus `…`.
  Two lines at 23px is roughly 70 chars; Dutch outlet titles routinely exceed it
  and CSS clipping breaks mid-word.
- `age_label` is precomputed server-side so the frontend does no date maths.
- `meta` carries a source-specific string where one exists (e.g. `"214 points"`
  for Hacker News), otherwise null and the view falls back to `age_label`.
- `new_count` = items first seen since the previous fetch.
- Group order and item limits come from `config.yaml`.
- `feed_count` is the number of feeds polled, for the footer. Counted from
  config, so a feed that returned nothing is still reflected.

**Feed fairness.** A group has more feeds than slots — "Self-hosted, Apple &
Linux" has five feeds and three slots. Sorting the union by recency lets one
prolific feed take the whole card: 9to5Mac publishes on the order of a hundred
items a day against a handful from It's FOSS, and in testing it filled all three
slots outright.

Selection is therefore round-robin across feeds — every feed offers its newest
unused item before any feed offers a second, so no feed appears twice while
enough feeds have items. The starting feed advances each fetch (offset stored in
`cache` under `news_offsets`), so a feed starved on one fetch leads the next.
Over five fetches of that five-feed group, each feed appears exactly three times.
The chosen items are then re-sorted newest-first for display.

**`GET /api/nas`**
```json
{
  "as_of": "2026-09-18T21:14:00+02:00",
  "stale": false,
  "host": "dev-minotaur", "uptime_seconds": 3650400,
  "storage": {
    "used_bytes": 8785411117056, "total_bytes": 14436769202176,
    "used_pct": 60.9, "free_bytes": 5651358085120,
    "pools": [
      { "name": "volume2", "used_bytes": 5897747951616, "total_bytes": 5984651051008,
        "used_pct": 98.5, "free_bytes": 86903099392, "projection_months": 0.6 }
    ]
  },
  "cpu_pct": 12, "ram_pct": 41, "cpu_temp_c": 38,
  "containers": { "running": 14, "total": 15 },
  "disks": [{ "name": "sda", "temp_c": 36, "smart": "ok" }],
  "network": {
    "rx_mbps": 12.4, "tx_mbps": 3.1,
    "history": [{ "t": "2026-09-17T21:00:00+02:00", "rx": 8.1, "tx": 2.0 }]
  },
  "backup": { "status": "ok", "at": "2026-09-18T03:12:00+02:00" }
}
```
`disks[].smart` is one of `ok` | `warn` | `fail`, driving the chip colour.

**The view renders one bar per pool, not the aggregate.** The aggregate is kept
in the payload but is misleading on its own: at the time of writing it reads a
comfortable 60.9% while `/volume2` sits at 98.5% with 87 GB free. Pools are
sorted fullest-first so the one at risk leads the card.

`projection_months` is per pool: free space ÷ mean daily growth from the
`storage_sample` table. Omitted entirely when there is under a week of history,
or when usage is flat or shrinking. The aggregate's own `projection_months` is
always omitted — only the per-pool figure is meaningful.

`network.history` is downsampled server-side to 144 points (10-minute buckets).
At the 60s sample cadence the raw 24h series is 1440 points, roughly 100 KB of
JSON per poll for a sparkline under 600px wide. Buckets are averaged rather than
sampled so brief spikes survive. Rates are **megabits** per second.

### config.yaml

```yaml
timezone: Europe/Amsterdam
currency: EUR

ghostfolio:
  base_url: http://ghostfolio:3333
  security_token: ${GHOSTFOLIO_TOKEN}

prices:
  provider: twelvedata
  api_key: ${TWELVEDATA_API_KEY}
  fallback: yfinance

news:
  max_per_group: 3
  title_max_chars: 70
  # `name` is the chip on the card, set explicitly rather than derived from the
  # feed's own title — those range from "9to5Mac" to "Tweakers Mixed RSS Feed".
  # A bare URL is also accepted, in which case the feed title is used.
  groups:
    - id: tech
      title: "Tech"
      feeds:
        - { url: "https://www.theverge.com/rss/index.xml", name: "The Verge" }
        - { url: "https://feeds.arstechnica.com/arstechnica/index", name: "Ars Technica" }
        - { url: "https://www.tomshardware.com/feeds/all", name: "Tom's Hardware" }
        - { url: "https://feeds.bloomberg.com/technology/news.rss", name: "Bloomberg" }
    - id: nl
      title: "Nederland"
      feeds:
        - { url: "https://feeds.nos.nl/nosnieuwsalgemeen", name: "NOS" }
        - { url: "https://www.nu.nl/rss/Algemeen", name: "NU.nl" }
        - { url: "https://www.nu.nl/rss/Economie", name: "NU.nl" }
    - id: home
      title: "Self-hosted, Apple & Linux"
      feeds:
        - { url: "https://hnrss.org/frontpage", name: "Hacker News" }
        - { url: "https://tweakers.net/feeds/mixed.xml", name: "Tweakers" }
        - { url: "https://9to5mac.com/feed/", name: "9to5Mac" }
        - { url: "https://www.omgubuntu.co.uk/feed/", name: "OMG! Ubuntu" }
        - { url: "https://itsfoss.com/rss/", name: "It's FOSS" }

readeck:
  # In the stack, the compose service name on its internal port. The default is
  # the published one (Readeck listens on 8000, taken by the collector, so it is
  # mapped to 8084) for running the collector off-NAS.
  base_url: ${READECK_URL:-http://100.70.0.10:8084}
  api_token: ${READECK_TOKEN}

nas:
  # NAS_HOST is 127.0.0.1 in the deployed container, the Tailscale address when
  # the collector runs from a laptop.
  node_exporter: http://${NAS_HOST:-100.70.0.10}:9100/metrics
  # Disk temps and SMART come from the Scrutiny container already on the NAS.
  # smartctl_exporter is therefore not deployed, and ugosbridge is not used —
  # node_exporter sees the UGOS pools as ordinary btrfs filesystems.
  scrutiny: http://${NAS_HOST:-100.70.0.10}:8080
  docker_socket: /var/run/docker.sock
  backup_marker: /volume1/docker/rclone/config/.backup_status
  storage_mountpoints: ["/volume1", "/volume2", "/volume3", "/volume4"]
  network_interface: eth0
```

`FD` and the Reuters agency feeds were in the original draft but return 404 —
FD has no free RSS. Bloomberg Technology serves headlines but paywalled bodies,
so tap-to-save will save a stub for those; that is expected, not a bug.

Two feeds needed replacing after checking **freshness**, not just that they
returned items: the Tweakers feedburner mirror had not updated since April 2025
(newest entry ~12,000 hours old) and is replaced by `tweakers.net` directly.
OMG! Ubuntu returns **429** under rapid polling — fine at the 10-minute cadence,
but worth remembering if it ever goes quiet. A feed that fails is logged and
skipped; one dead source never blanks the view.

---

## 6. Data sources

### Ghostfolio

Self-hosted, official images for amd64 and arm64, Postgres + Redis.
Auth: `POST /api/v1/auth/anonymous` with the account's security token returns a
bearer token; send it as `Authorization: Bearer …` on every request.
Cache the token and refresh on 401.

**Endpoints discovered against a running instance**, as warned — several paths
in the older documentation are gone:

| Path | Status |
|---|---|
| `POST /api/v1/user` | creates an account, returns the security token |
| `POST /api/v1/auth/anonymous` | security token → bearer JWT. Works as described |
| `GET /api/v1/portfolio/details` | ✅ `summary` + `holdings` |
| `GET /api/v2/portfolio/performance?range=…` | ✅ `performance` + daily `chart` |
| `POST /api/v1/import` | bulk activity import |
| `GET /api/v1/portfolio/performance` | **404 — v1 is gone, use v2** |
| `GET /api/v1/portfolio/positions` | **404 — gone** |
| `GET /api/v1/order` | **404 — gone** |

`holdings` is a **list**, not a symbol-keyed object as older versions returned,
and identity lives in a nested `assetProfile` (`symbol`, `name`, `currency`,
`assetClass`). Per-holding figures are `valueInBaseCurrency`,
`allocationInPercentage`, `quantity`, `marketPrice`, `netPerformancePercent`.

Ranges for `change`: `1d`, `1mo`, `1y`, `max` against the v2 performance
endpoint; its `chart` array (`date`, `value`) supplies `history`.

**Base currency must be set in the UI, not the environment.** Ghostfolio is
fully multi-currency and converts with an FX effect (`valueInBaseCurrency`,
`netPerformancePercentWithCurrencyEffect`), and its built-in default is
`DEFAULT_CURRENCY = 'USD'`. Six of the eleven holdings are USD-quoted, so this
has to be EUR or every figure on the screen is in dollars.

The `BASE_CURRENCY` environment variable **no longer exists** — it is listed as
a removed breaking change in Ghostfolio's own CHANGELOG, and the only mention
left in the image is that changelog entry. Set it under
**Settings → Base Currency** instead; it is a per-user setting.

**Ghostfolio does not expose a per-holding daily change.** It reports
performance since purchase only, and passing `range=1d` to
`/portfolio/details` or `/portfolio/holdings` changes nothing — verified
identical values for `1d`, `1y` and no range. This matters because
`/api/portfolio` specifies `holdings[].day_pct`, and the spotlight selection
rule depends on it.

The user enters holdings and transactions in Ghostfolio's own UI, or imports a
broker CSV. This project never writes to Ghostfolio.

### Setting it up, and keeping it current

`tools/degiro_to_ghostfolio.py` converts a DEGIRO **Transacties** export (not
the Portfolio export — that has no cost basis) into Ghostfolio's import format.

Two things bite on a fresh instance, both verified against a running copy:

1. **The base currency list is built from your data.** A new instance offers
   only `USD` and `USX`; `EUR` appears once an EUR-denominated activity exists.
   So import first, then set Settings → Base Currency.
2. **Exchange rates are not fetched until something asks for them.** Until then
   Ghostfolio adds USD and EUR as if 1:1 — a portfolio of EUR 8,362 reads as
   8,953. Fix with **Admin → Gather all data** once; `MarketData` then gains
   `USDEUR` rows and conversion works. Scheduled jobs (`EVERY_HOUR`,
   `EVERY_DAY_AT_MIDNIGHT`, weekly) keep it current afterwards.

**Ongoing workflow: re-export everything and re-import the whole file.**
Ghostfolio deduplicates on import — verified: importing the identical file
twice adds zero activities, and a file with one new trade appended adds exactly
that one. No need to track deltas.

Instruments that cannot be resolved by the data source are skipped with a
warning rather than silently dropped. Delisted holdings are the usual cause —
Just Eat Takeaway survives only as a USD ADR, whose price history would not
match EUR trades.

### Prices (spotlight only)

Free-tier limits as of now: Alpha Vantage roughly 25 requests/day, Finnhub
roughly 60/min, Twelve Data roughly 800/day, described on their pricing as 8 API
credits per minute and 800 per day.

Alpha Vantage is ruled out — 25/day is unusable. Twelve Data is primary because
it advertises wide global exchange coverage and these are Euronext tickers;
Finnhub's more generous rate limit is oriented to US listings.

Backoff behaviour differs: Finnhub returns a `Retry-After` header on 429,
typically 60 seconds, Alpha Vantage returns none. Implement client-side rate
limiting regardless and never rely on the header being present.

yfinance is the fallback only. It is unofficial, scrapes Yahoo's endpoints, may
breach their terms, and breaks periodically; its own documentation points users
at Yahoo's personal-use terms. Wrap it in try/except and expect it to fail.

Because Ghostfolio covers the portfolio view, the price API is called for one
ticker per cycle — comfortably inside any free tier.

### NAS metrics

UGOS Pro has Docker and SSH but no SNMP service, so the Synology SNMP approach
does not apply. Enable SSH under Settings → Remote Access; keep compose files
under `/volume1/docker` so they survive UI changes.

| Metric | Source |
|---|---|
| CPU, RAM, network, uptime, pool usage | `node_exporter` (needs host PID/net namespaces and `/host` mounts) |
| Disk temps, SMART status | **Scrutiny**, already running on `:8080` — `GET /api/summary`, no auth |
| Container counts | Docker socket, read-only mount |
| Backup status | `/volume1/docker/rclone/config/.backup_status`, written by `rclone/config/backup.sh` |

`smartctl_exporter` and `ugosbridge` were both in the original draft and neither
is deployed. Scrutiny already collects SMART data for all five SATA disks, which
removes the need for a second privileged container. And `node_exporter` does see
the UGOS pools — they appear as ordinary btrfs mounts on `/dev/mapper/ug_*`, so
the unofficial ugosbridge is unnecessary.

Two gaps this leaves: the **two NVMe drives are invisible to Scrutiny**, though
node_exporter reports their temperature via hwmon; and `sde` is a USB-attached
WD drive mounted at `/mnt/@usb`, so it is counted as a disk but is not a bay disk.

The backup marker is written by a `write_marker()` helper added to the existing
`backup.sh`, in the same success/failure branches that already notify Telegram
and Uptime Kuma. It lives under `/config/rclone` because that is the only
writable mount in the rclone container — `/data/docker` is `:ro`. The collector
needs that directory mounted read-only or the tile silently reads "unknown".

---

## 7. Design tokens

Lift from the artboards; reproduced here as the canonical list.

```css
:root {
  --bg:          #0A0B0D;
  --surface:     #121417;
  --surface-2:   #16191D;
  --chip:        #1A1D22;
  --border:      #1E2126;
  --hairline:    #191C20;

  --text:        #F2F4F6;
  --text-2:      #B9BEC5;
  --text-muted:  #8B9199;
  --inactive:    #2B3037;
  --inactive-2:  #3A4048;

  --green:       #46D68F;   /* portfolio accent, positive */
  --blue:        #5C7CFA;   /* NAS accent */
  --amber:       #E8B84B;   /* news accent, warn state */
  --red:         #F2555A;   /* negative */

  --radius-card: 20px;
  --radius-sm:   16px;
  --radius-tile: 12px;
  --radius-chip: 7px;
  --radius-pill: 999px;

  --pad-page-x:  40px;
  --pad-page-t:  40px;
  --pad-page-b:  36px;
  --pad-card:    24px;
  --gap-card:    14px;
}
```

- Accent-soft fills (pill backgrounds, chart areas) are the accent at **13% alpha**.
- Type: Instrument Sans 400/500/600/700 for everything; JetBrains Mono 400/500
  for uppercase micro-labels, ticker chips and timestamps only.
- Scale: hero 76 / 60, section 44 / 32, card title 17 (600), body 15, label 14–13,
  micro mono 12–11.
- Negative tracking on large figures: −0.035em at 60px+, −0.03em at 44px, −0.02em at 26–32px.
- `font-variant-numeric: tabular-nums` on **every** figure. Non-tabular digits
  jitter on a screen that refreshes in place.
- Each view has its own accent so the current screen is identifiable before
  reading: portfolio green, news amber, NAS blue.

**Self-host the fonts.** The artboards load them from Google Fonts; the kiosk
must not depend on internet access. Download the woff2 files into
`dashboard/assets/fonts/` and `@font-face` them locally.

---

## 8. Frontend

Vanilla HTML/CSS/JS. No framework, no build step. Each view is a standalone
HTML fragment fetched by the shell.

### Carousel

- Fixed equal loop: portfolio → spotlight → news → NAS → repeat.
- Default 20 s per view, configurable in one constant.
- Cross-fade of 400 ms between views; no sliding or scaling.
- The footer pill fills over the view's duration as a progress indicator,
  then the next dot becomes the pill.
- Data is fetched independently of the rotation, on the collector's cadence —
  a view never shows a loading state, only the last good data.

### Touch

**No navigation.** The rotation is entirely automatic — there is no previous,
next, or pause. Views are given a long enough dwell time to act on what is on
screen. Touch exists only for per-view *actions*, so a tap is never ambiguous
between "page" and "do something".

| View | Tap target | Action |
|---|---|---|
| News | A headline | Save the article to Readeck to read later |
| Portfolio | — | none yet |
| Spotlight | — | none yet |
| NAS | — | none yet |

Tapping must give immediate visual feedback — the row acknowledges the touch and
reports success or failure in place. A save that fails silently is worse than no
tap target at all, because the article is then lost rather than deferred.

Open question for the news step: whether a tap should briefly hold the current
view, so the rotation does not move on mid-interaction.

### Readeck

Self-hosted read-later service on the NAS. The collector exposes `POST /api/save`;
the frontend posts the article URL to it and the collector forwards it to
Readeck's API with a token from the environment (`.env`, loaded via `env_file`).
Readeck does its own article extraction, so the collector needs no readability
library.

Contract, verified against Readeck 0.23.4 — **not** what older documentation
describes, which is why it was probed against a running instance:

- `POST /api/bookmarks`, `Authorization: Bearer <token>`, body `{"url", "title", "labels"}`
- **`202 Accepted`** on success, with a `Bookmark-Id` header. Readeck *queues*
  the link and fetches it afterwards, so a save means accepted, not extracted —
  a paywalled page still returns 202 and fails later, out of view of the screen.
- `401` invalid token, `422` missing url.
- There is no `/api/auth` in this version; tokens are created in the web UI
  under Profile → API tokens. The token needs **only** the `bookmarks:write`
  role — confirmed by getting 403 when listing bookmarks with a write-only token.

The collector logs a warning at startup when `READECK_TOKEN` is unset, since an
unset `${VAR}` expands to an empty string and would otherwise only surface as a
failed tap much later.

This is the **only** write path in the project, and it is LAN-only and triggered
by a physical tap. Paywalled sources (Bloomberg) will save a stub — expected.

### States every view must handle

| State | Rendering |
|---|---|
| `stale: true` | Timestamp in the footer turns amber, prefixed "STALE" |
| Collector unreachable | Full-screen fallback in the same design language: "Collector unreachable since HH:MM". Never a browser error page. |
| Empty group (news) | Group card is omitted, remaining cards expand |
| Fewer than 5 holdings | List shrinks, card does not stretch |

---

## 9. Kiosk setup (Pi)

- DietPi with the Chromium kiosk option, or Raspberry Pi OS Lite + `cage`.
  Raspberry Pi OS is Wayland now — X11 guides (`xset s off`, `unclutter`) do not apply.
- Chromium flags:
  `--kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble
   --incognito --check-for-update-interval=31536000 --app=http://<nas>:8083/`
- `kiosk.service`: systemd unit, `Restart=always`.
- Nightly Chromium restart via systemd timer at 04:00 — it leaks memory over days.
- `brightness.py`: writes `/sys/class/backlight/*/brightness` on a schedule.
  Sunset-based rather than fixed clock times. `TODO(user)` for levels and behaviour.
- `log2ram` to spare the SD card, or boot from USB SSD.

---

## 10. Build order

| Milestone | Deliverable | Status |
|---|---|---|
| M1 | Collector skeleton + `/api/nas` from exporters. No API keys needed — fastest path to real data. | **done** — deployed on the NAS, image published to Docker Hub via GitHub Actions |
| M2 | Four static views rendering against fixture JSON, carousel working, viewed in a desktop browser at 720×1280. | in progress — fixtures, shell, rotation, NAS and portfolio views done; spotlight and news to go |
| M3 | Ghostfolio wired up, `/api/portfolio` live. | |
| M4 | `/api/spotlight` with the price API, `/api/news` with feeds. | |
| M5 | Pi flashed, kiosk running, display mounted. | |
| M6 | Dimming, watchdog, stale and fallback states, tap-to-save. | |

M1 and M2 are independent — the fixture JSON in M2 doubles as the schema
contract and as test data.

### Deployment

The collector image is built and pushed by GitHub Actions on every push to
`main`, tagged `:latest` and `:<sha>`, following the same pattern as `stock-bot`
in the `nas-docker` repo. Watchtower picks up new tags, so a merge eventually
becomes a running container with no manual step. `config.yaml` is baked into the
image, which keeps git authoritative but means a feed change needs a CI round
trip rather than an edit on the NAS.

---

## 11. Non-goals

- No internet exposure, no TLS, no auth. LAN-only.
- No writes anywhere, with one deliberate exception: tapping a headline saves it
  to Readeck on the same LAN. See §8.
- No alerting, no historical analytics beyond the two sparklines.
- No writes to Ghostfolio.
- No trading, no order entry, no recommendations.