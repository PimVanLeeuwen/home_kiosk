# Home hub: plan

home_kiosk grows from a 720×1280 desk carousel into **Home hub**: the household's main website
for news, portfolio, NAS and Docker health, backups, service links and all Telegram alerts. One
responsive app for laptop and mobile, with viewing and managing in the same place. The Pi kiosk
keeps running throughout.

The original kiosk build spec (Pi hardware, kiosk setup, Ghostfolio pitfalls, collector
endpoints) is kept as-is in [docs/kiosk-build-spec.md](docs/kiosk-build-spec.md).

Approved mockups (2026-09-30): Home, News (list + reader), Alerts. Screenshots live outside the
repo in `~/Pictures/pr-screenshots/home_kiosk/2026-09-30-mockups/`.

---

## 1. Decisions

| Topic | Decision |
|---|---|
| Backend | Keep the Python collector (FastAPI + APScheduler + SQLite), grown into the hub API. No Spring Boot, no MariaDB. |
| Frontend | New `web/` app: React + TypeScript + Vite + Tailwind + React Router, same family as community-cafe-web. |
| Serving | The existing Caddy `dashboard` image on :8083 serves `web/` at `/`, the old carousel at `/kiosk/`, and proxies `/api/*`. |
| Access | No login. The network is the boundary: LAN and Tailscale only, never through cloudflared. |
| HTTPS | `tailscale serve` (nas-docker `tailscale/serve.json`): the hub on 443, each service on its port plus 10000, so the plain `http://100.x:<port>` addresses keep working. Links read the served ports from tailscaled. Transmission stays HTTP. |
| Link hosts | Chosen in the browser from `location.hostname`: `*.ts.net` or `100.x` means Tailscale links, anything else means LAN links (`192.168.1.10`). |
| Style | Dark first. "Calm graphite": near-black, darker sidebar, page in a raised rounded panel, violet accent (`#7C6CF2`), comfortable density. |
| Type | Instrument Sans with tabular figures for all numbers. JetBrains Mono only for technical values (container names, hosts, commands). Both self-hosted. |
| Navigation | Laptop: fixed left sidebar with grouped sections (Home / Read / Money / House / System). Mobile: bottom tab bar (Home, News, Portfolio, NAS, More). |
| Brand | Text only: "Home hub" with the NAS host name as subtitle. No logo. |
| Settings | Editable in the app, stored in SQLite. `config.yaml` only seeds defaults on first start. |
| Article reading | Backend extraction with trafilatura, cached in SQLite; falls back to "Open original". Readeck stays as "Save for later". |
| Search | News only. |
| Container actions | Out of scope; use Dockge. The Docker socket stays read-only. |
| Pi kiosk controls | Out of scope for now (dimming, rotation choice). |
| Service logins | Sonarr, Radarr, Prowlarr: "Disabled for Local Addresses" plus "Trust CGNAT IP Addresses" (covers Tailscale). Apps with real accounts rely on long-lived sessions plus a password manager. No SSO for now. |
| Bookmarks | External links live in the service catalog (a `url` instead of a port), editable in Settings; homepage's three bookmarks were migrated. |
| Telegram | The hub owns the bot token (NAS-only `.env`). Two chats, as today: **NAS alerts** and **Portfolio**. The bot only accepts commands from those chats. |

## 2. Architecture

```
                 ┌──────────── NAS (Docker) ────────────┐
 browser ──LAN──►│ dashboard (Caddy :8083)              │
 phone ──TS────► │   /        → web/ (React)            │
 Pi kiosk ──────►│   /kiosk/  → old carousel            │
                 │   /api/*   → hub API (:8000)         │
                 │                                      │
                 │ hub API (Python, SQLite)             │
                 │   sources: ghostfolio, feeds, nas,   │
                 │   docker, scrutiny, readeck, arr/    │
                 │   jellyfin/immich widgets, backups   │
                 │   jobs: collectors, alert rules,     │
                 │   reports, Telegram bot (polling)    │
                 └──────────────┬───────────────────────┘
   backup.sh ── POST /api/notify, /api/backup/runs ──┘
   watchtower ─ shoutrrr generic webhook ───────────┘
   uptime-kuma  webhook notification ───────────────┘
```

Telegram uses long polling (`getUpdates`), so no inbound webhook and no public URL is needed.

## 3. Milestones

Each milestone is a series of small steps. Every step: tests, build and lint green, one proposed
commit message, screenshots for visual changes.

**M1. Foundation**
- `web/` app shell: sidebar and bottom tab bar, routes for every section (empty states), design
  tokens from the mockups, self-hosted fonts.
- Caddy: `web/` at `/`, carousel at `/kiosk/`. Existing `/api/*` responses unchanged.
- Tests: pytest for the backend (starting with the existing sources), Vitest + Testing Library for
  `web/`, Playwright (desktop + mobile) in `e2e/`.
- CI: lint and test both parts, build both images as today.

**M2. Home, services and links** (retires homepage). **Done 2026-09-30.**
- Service catalog (name, group, icon, port, container, widget type), editable in Settings.
- LAN / Tailscale link resolution; `tailscale serve` HTTPS per service.
- Status from the Docker socket plus an HTTP check.
- Widget adapters one per service: Jellyfin, Immich, Jellyseerr, Sonarr, Radarr, Bazarr,
  Prowlarr, Transmission, SABnzbd, Uptime Kuma, Scrutiny. API keys in the hub `.env`.
- Home page per the mockup. Then the homepage stack is removed from nas-docker.

**M3. NAS and Docker**. **Done 2026-10-01.**
- Host metrics and storage runway (existing), disk health from Scrutiny.
- Per-container CPU, memory and network from the Docker stats API, 24h history.
- Image update history: the hub notices when a container is recreated from a new image (Watchtower
  or Dockge), so no Watchtower webhook is needed.

**M4. Backups**. **Done 2026-10-01.**
- `backup.sh` appends a JSON run record (per volume: result, duration, bytes, errors) to
  `rclone/config/backup-runs.jsonl`, which the collector reads from its read-only mount.
- Backups page: run history, last success per volume, trends. Kuma heartbeat stays.

**M5. Telegram hub**. **Done 2026-10-01.** Decided 2026-10-01: Uptime Kuma keeps its own direct Telegram line for
"hub down" and the backup heartbeat; a problem sends one message when it starts and one when it is
resolved; quiet hours 23:00 to 07:00 hold non-errors for one digest at 07:00; senders post to
`/api/notify` with a shared `NOTIFY_KEY`; the existing bot is kept; bot commands
`/status`, `/backup`, `/portfolio`, for members of the two chats only; rule defaults as below.
- `POST /api/notify` (source, severity, title, body), message log, routing per category to chat,
  templates, quiet hours (errors bypass), compose and send.
- Hub alert rules: disk above 90%, container unhealthy or restart loop, backup missing for 26h,
  SMART warning, optional portfolio move.
- Two-way bot: `/status`, `/portfolio`, `/backup`, `/mute`.
- Migrate senders one at a time: backup.sh, watchtower, Uptime Kuma, Scrutiny. Then remove the
  token from nas-docker and rotate it in BotFather.

**M6. News reader**. **Done 2026-10-02.**
- Full feed list with group filters, read/unread state, news search, trafilatura reader, Readeck
  save. Feeds editable in Settings.
- Decided 2026-10-01: articles kept 7 days; read state shared and set on open; images proxied by
  the hub; the reader gets text blocks only, never site HTML; the link and every redirect must be
  a public address. Saved lists unarchived Readeck bookmarks (Archived filter), reads them in the
  same reader, offers archive and delete (Readeck's own scheduled delete) and syncs read progress.

**M7. Portfolio**. **Done 2026-10-02.**
- Full Ghostfolio overview: value history, holdings, allocation, holding detail.
- Daily report through M5, which makes stock-bot redundant (retirement when the owner says so).
- Added 2026-10-01: upload a full DEGIRO transaction export on the Portfolio page to bring the
  portfolio up to date, built to need minimal effort when DEGIRO changes its export.
- Decided 2026-10-02: the upload goes into Ghostfolio (Transactions export only). The hub shows a
  preview (new, already there, unknown product) and imports only new orders after confirmation,
  each tagged with its DEGIRO order ID. Existing activities came from a CSV import without those
  IDs, so the hub matches on day, product, type, quantity and price rather than Ghostfolio's
  exact-match check. Columns are found by header name (English and Dutch). The daily report runs
  like stock-bot: 08:30 and 18:30 on weekdays, holdings plus the S&P 500, Nasdaq 100 and AEX.

**M8. Cleanup**. **Done 2026-10-02.**
- Retire stock-bot (removed from nas-docker), update the
  READMEs, copy the stack into nas-docker, and remove the old DEGIRO converter script.
- The `/kiosk/` restyle is postponed: the Pi kiosk is not in use yet.

**M9. Repos** (added 2026-10-01)
- A "Code" sidebar group with a Repos page: tabs Mine (PimVanLeeuwen), Hubble
  (Hubble-Community-Cafe) and GEWIS (only repos with your pull requests or commits). Private repos
  included through read-only fine-grained tokens, one per owner.
- Per repo: description, language, stars and forks, visibility, last push, open pull requests and
  issues, CI state of the default branch, latest release. Archived repos hidden.
- One GraphQL query per owner every 30 minutes, cached; the last good list stays on errors.

**M10. GitHub mirror** (added 2026-10-04)
- A backup of the git history in case GitHub goes away: every repo of PimVanLeeuwen and
  Hubble-Community-Cafe (no forks, archived ones included), nothing of GEWIS. Issues and pull
  requests are not kept.
- Runs in the collector (it already has the tokens and the owner list), nightly at 02:00 and right
  after a start that missed a night. Bare `git clone --mirror` per repo in
  `/volume3/backups/github/<owner>/<repo>.git`, which the 03:00 rclone run takes to Hetzner.
- An exact copy, by choice: a repo deleted on GitHub is deleted from the mirror, and force-pushes
  overwrite history. No protection against git mistakes.
- The hub's read-only tokens are reused; git gets them as an HTTP header through the environment,
  so they are never written into the mirrors (or the backup).
- Shown on the Backups page (a GitHub mirror card) and per repo on the Repos page. A failed run
  sends a Telegram message; the backup_missing rule also covers the mirror, and `/backup` lists it.

Order: M1, M2, M3 + M4, M5, M6, M7, M8. M9 slotted in after M2, M10 after M8.

## 4. Open items

- Pi kiosk URL: the carousel now lives at `/kiosk/`, so the Pi's Chromium `--app` URL becomes
  `http://<nas>:8083/kiosk/?data=api`. Without `?data=api` the carousel shows its fixture data.
  `/kiosk` and the old `/read.html` redirect.

## 5. Non-goals

- No internet exposure, no login, no SSO (for now).
- No container control; Dockge does that.
- No trading, order entry or investment recommendations. The only writes to Ghostfolio are
  confirmed DEGIRO imports (M7).
