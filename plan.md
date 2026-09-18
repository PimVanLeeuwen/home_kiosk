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

1. **Ugreen model** — exact model, Intel or ARM, disk count, RAID level.
   ARM models cannot pull x86 images; verify before choosing image tags.
2. **Existing services on the NAS** — Portainer, reverse proxy, Tailscale,
   and anything already bound to ports 3000 / 8080 / 9090.
3. **Holdings** — entered into Ghostfolio by the user, not by this project.
4. **Broker CSV export** — used for the initial Ghostfolio import.
5. **RSS feed URLs** — grouped by topic. See `collector/config.yaml` schema below.
6. **Night behaviour** — dim / off / always on, and at what times.
7. **Hardware owned?** — if not, see shopping list in §3.

---

## 3. Hardware

| Item | Spec | Note |
|---|---|---|
| Raspberry Pi 5 | 4GB | Pi 4 2GB also fine; Pi Zero 2 W is not |
| Raspberry Pi Touch Display 2 | 7", 720 × 1280 | Natively portrait, matches the design 1:1 |
| PSU | Official 27W USB-C | Display draws power from the Pi's GPIO header |
| Storage | 32GB A2 microSD, or small USB SSD | SSD preferred for write endurance |
| Stand | SmartiPi or 3D print | — |

Display connects by DSI ribbon plus a 3-pin GPIO power lead. Backlight
brightness is a writable file under `/sys/class/backlight/` — locate the exact
node at setup time, it varies.

---

## 4. Architecture

```
┌─────────────────────── Ugreen NAS (Docker) ───────────────────────┐
│                                                                    │
│  ghostfolio ──┐                                                    │
│  postgres     │                                                    │
│  redis        │                                                    │
│               ├──► collector (Python) ──► SQLite ──┐               │
│  node_exporter│         │                          │               │
│  smartctl_exp ┘         └──► /api/*.json ──────────┤               │
│  ugosbridge                                        │               │
│                                                    ▼               │
│                                          caddy ──► dashboard/      │
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
│   ├── views/
│   │   ├── portfolio.html
│   │   ├── spotlight.html
│   │   ├── news.html
│   │   └── nas.html
│   └── assets/
│       ├── tokens.css
│       ├── app.js
│       └── fonts/               # self-hosted woff2, see §8
├── caddy/Caddyfile
└── kiosk/                       # Pi-side setup, see §9
    ├── setup.sh
    ├── kiosk.service
    └── brightness.py
```

---

## 5. Collector

Python 3.12, FastAPI + APScheduler, SQLite via plain `sqlite3`.
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
- `cache(key PK, payload_json, fetched_at)` — last-good response per endpoint

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
Selection rule: largest absolute `day_pct` among holdings, cash excluded,
ties broken by position value. `history` is ~52 weekly points.
`next_earnings` is optional — omit the field entirely if unavailable, and the
view hides that cell rather than showing a dash.

**`GET /api/news`**
```json
{
  "as_of": "2026-09-18T21:12:00+02:00",
  "stale": false,
  "groups": [
    {
      "id": "semis", "title": "Semiconductors & AI", "new_count": 3,
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

**`GET /api/nas`**
```json
{
  "as_of": "2026-09-18T21:14:00+02:00",
  "stale": false,
  "host": "tower", "uptime_seconds": 3650400,
  "storage": {
    "used_bytes": 15613000000000, "total_bytes": 23970000000000,
    "used_pct": 65, "free_bytes": 8357000000000, "projection_months": 14
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
`projection_months` = free space ÷ mean daily growth over the snapshot window;
omit if there is under a week of history.

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
  groups:
    - id: semis
      title: "Semiconductors & AI"
      feeds:
        - https://…   # TODO(user)
    - id: nl
      title: "Nederland"
      feeds: []       # TODO(user) — NOS, NU.nl, FD
    - id: tech
      title: "Self-hosted & tech"
      feeds: []       # TODO(user) — HN, Tweakers

nas:
  node_exporter: http://node-exporter:9100/metrics
  smartctl_exporter: http://smartctl-exporter:9633/metrics
  ugosbridge: http://ugosbridge:9105/metrics
  backup_marker: /data/backup/.last_success   # TODO(user) — confirm path
```

---

## 6. Data sources

### Ghostfolio

Self-hosted, official images for amd64 and arm64, Postgres + Redis.
Auth: `POST /api/v1/auth/anonymous` with the account's security token returns a
bearer token; send it as `Authorization: Bearer …` on every request.
Cache the token and refresh on 401.

**Discover the exact portfolio endpoints against the running instance** rather
than hardcoding paths from documentation — they have moved between versions.
Ghostfolio supplies total value, day change, performance figures and holdings
with weights, which covers nearly all of `/api/portfolio`.

The user enters holdings and transactions in Ghostfolio's own UI, or imports a
broker CSV. This project never writes to Ghostfolio.

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
| CPU, RAM, network, uptime | `node_exporter` (needs host PID/net namespaces and `/host` mounts) |
| Disk temps, SMART status | `smartctl_exporter` (privileged, device access) |
| Pool usage, RAID state | `ugosbridge` — unofficial UGOS exporter, not affiliated with Ugreen |
| Container counts | Docker socket, read-only mount |
| Backup status | mtime of a marker file — `TODO(user)` confirm path |

Generic `node_exporter` sees filesystems, not UGOS's pool abstraction, which is
why ugosbridge is in the stack. If it proves unreliable, fall back to
filesystem-level numbers for the storage hero and accept they are approximate.

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

The panel is capacitive. Tap left third = previous, right third = next,
centre = pause/resume with the pill frozen. Nothing else is interactive.

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
   --incognito --check-for-update-interval=31536000 --app=http://<nas>:8080/`
- `kiosk.service`: systemd unit, `Restart=always`.
- Nightly Chromium restart via systemd timer at 04:00 — it leaks memory over days.
- `brightness.py`: writes `/sys/class/backlight/*/brightness` on a schedule.
  Sunset-based rather than fixed clock times. `TODO(user)` for levels and behaviour.
- `log2ram` to spare the SD card, or boot from USB SSD.

---

## 10. Build order

| Milestone | Deliverable |
|---|---|
| M1 | Collector skeleton + `/api/nas` from exporters. No API keys needed — fastest path to real data. |
| M2 | Four static views rendering against fixture JSON, carousel working, viewed in a desktop browser at 720×1280. |
| M3 | Ghostfolio wired up, `/api/portfolio` live. |
| M4 | `/api/spotlight` with the price API, `/api/news` with feeds. |
| M5 | Pi flashed, kiosk running, display mounted. |
| M6 | Dimming, watchdog, stale and fallback states, touch controls. |

M1 and M2 are independent — the fixture JSON in M2 doubles as the schema
contract and as test data.

---

## 11. Non-goals

- No internet exposure, no TLS, no auth. LAN-only.
- No alerting, no historical analytics beyond the two sparklines.
- No writes to Ghostfolio.
- No trading, no order entry, no recommendations.