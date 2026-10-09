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

**M11. Message templates** (added 2026-10-04)
- Settings → Messages: the wording of the alert rules (and Resolved), the portfolio report, the
  GitHub mirror failure, and the messages from the NAS (backup, Watchtower, Uptime Kuma) is
  editable. Bot replies and messages typed on the Alerts page are not.
- One text per message with `{placeholders}` and `<b> <i> <u> <s> <code> <pre>`; repeating parts
  (holdings, indices, backup volumes, updated containers) have their own line template. Values are
  escaped; a line holding only an empty placeholder is left out.
- Only changes are stored (alert setting `templates`); the built-in texts give the messages from
  before. Saving checks placeholders, tags and Telegram's length limit. The editor previews with
  sample values (rendered by the hub) and can send a test to the message's chat, quiet hours or not.
- backup.sh sends its figures in `data`; Watchtower's report lines are read back. Anything the hub
  cannot read goes out as the sender wrote it.
- No emoji (decided 2026-10-08). Telegram has no colours, so the severity is a bold word before
  the title (`{level}`: ERROR, WARNING, OK, INFO) and the portfolio report's holdings and indices
  are one monospace `<pre>` table with padded values; the + and − signs carry the direction.
  Telegram allows no tags inside `<pre>`, so saving checks that too. Texts saved with the old
  `{icon}` and `{dot}` placeholders are rewritten when read.

**M12. Backup hardening** (added 2026-10-08)
- Done 2026-10-08, outside the code: automatic snapshots on the Hetzner Storage Box (Robot). The
  NAS's sftp login cannot delete them, so a bad state that reaches Hetzner by `rclone sync` can
  still be rolled back. RECOVERY.md gets the restore steps from a snapshot.
- Consistent database copies: before the 03:00 sync, a host job on the NAS (outside Docker)
  dumps every live database to a file the sync then takes along: `pg_dump` for Ghostfolio,
  Tandoor and Tracearr through `docker exec`, and a CouchDB dump. The collector writes its own
  SQLite copy with `VACUUM INTO` into its data folder. So neither the rclone container nor the
  collector needs more Docker access (decided 2026-10-09). The job appends a run record with a
  `dumps` entry per database (result, size), shown on the Backups page; a failed dump is an
  error alert.
- Uptime Kuma and Tracearr move from named volumes to bind mounts under `/volume1/docker`, so
  the nightly backup covers them. RECOVERY.md's "not backed up" rows go.
- Restore check, monthly (`host-jobs/restore-check.sh`, root's crontab, the 1st at 05:00):
  downloads the database dumps and the hub's database copy from Hetzner and compares them byte
  for byte with the local files, then restores the Ghostfolio dump into a throwaway Postgres and
  opens the hub copy in a throwaway collector container (the live images, no network). Each run
  is a record in `restore-checks.jsonl`; the Backups page shows "last verified restore" and the
  backup_missing rule warns when the newest check failed or the last good one is older than 45
  days (editable).
- Storage Box space on the Backups page: used and free from `rclone about`, with the same runway
  projection as the NAS storage, and an alert above 85%.

**M13. Health and expiry alerts** (added 2026-10-08). **Done 2026-10-09.**
- Token expiry: GitHub returns `github-authentication-token-expiration` on every API call. The
  hub keeps it per token (Repos and the mirror) and alerts 14 days before, and again at 3 days.
  Shown on the Repos page. (Tailscale keys do not expire on this tailnet, so no rule for them.)
- UPS: the Ugreen US3000 (a DC UPS) is on USB to the NAS. Checked 2026-10-09: UGOS protection
  mode is Standby (below 15% battery it stops all services; the NAS powers off when the battery
  is empty), and its NUT server is on and reachable from the collector as
  `ups0@host.docker.internal:3493`, no login needed. The collector reads `ups.status`,
  `battery.charge`, `battery.charge.low` and `ups.load`. `battery.runtime` reads 65535 (no real
  value) and the voltages are DC, so neither is shown. A tile on the NAS page. Low battery is
  `LB` or charge at or below `battery.charge.low` (the driver runs with `ignorelb`).
- The router is not on a UPS, so alerts cannot reach Telegram during a power cut. The hub
  records each outage (start, end, lowest charge, whether it reached the 15% stop) and sends one
  message when power and internet are back. UGOS "Auto power-on when power is supplied" must be
  on, or the NAS stays off after a full drain.
- Compose healthchecks for the collector (`/api/health`, run with Python, so no curl in the
  image) and the dashboard (Caddy, with `wget`), so the existing "container unhealthy" rule
  covers the hub itself.

**M14. Privacy hardening** (added 2026-10-08). **Done 2026-10-09.**
- Exposure audit, in two parts (decided 2026-10-09). The tunnel connects outward, so the router
  needs no open port and only Tandoor (`recipes.example.com`) and CouchDB may be public.
  1. The collector, every 6 hours, with a read-only Cloudflare API token: the zone's DNS records
     and every tunnel's hostnames; anything that leads to the house (a tunnel route, a CNAME to a
     tunnel, an A/AAAA record on the home IP) and is not on the allowlist is an error alert. Each
     such hostname is also requested over HTTPS, through Cloudflare, as an outsider would.
  2. A nightly GitHub workflow (`exposure-scan`) for the ports: the home IP is dynamic, so the
     runner joins the tailnet as a temporary node (`tag:exposure-scan`, the policy lets it reach
     only the hub's API), asks the hub for the IP, scans every TCP port over the internet and posts
     the result back. Any open port is an error alert, no good scan in 48 h a warning.
  Both show on the NAS page's Exposure card.
- No Docker socket proxy (decided 2026-10-09): not worth the setup for a LAN-only stack.

**M15. Weather and app** (added 2026-10-08). **Done 2026-10-09.**
- Buienradar for the home spot: rain in the next 2 hours from
  `gpsgadget.buienradar.nl/data/raintext?lat=52.11&lon=5.18` (5-minute steps) as a bar chart,
  and current weather from the nearest station in `data.buienradar.nl/2.0/feed/json`. Fetched
  by the collector every 5 minutes, cached with `as_of` and `stale`; a Home tile. Buienradar asks
  for attribution, so the tile names it. A kiosk slide waits for the kiosk restyle (M8).
- The hub as a real PWA, replacing today's plain "Add to Home Screen" bookmark: a web app
  manifest (`display: standalone`, name, icons, theme colour), iOS safe-area padding, and a
  service worker that caches the app shell and the last API payloads, so the app opens offline
  and shows them as stale. No web push: alerts stay on Telegram. Installed from the Tailscale
  HTTPS address (`*.ts.net`): browsers only run service workers over HTTPS, so on the plain LAN
  address the hub works as before, without offline mode. The service worker leaves `/kiosk/`
  alone. The existing home screen icon has to be removed and added again from the ts.net
  address.

Order: M1, M2, M3 + M4, M5, M6, M7, M8. M9 slotted in after M2, M10 after M8, then M11. Then
M12, M13, M14, M15.

## 4. Open items

- Pi kiosk URL: the carousel now lives at `/kiosk/`, so the Pi's Chromium `--app` URL becomes
  `http://<nas>:8083/kiosk/?data=api`. Without `?data=api` the carousel shows its fixture data.
  `/kiosk` and the old `/read.html` redirect.
- Ad and tracker blocking (DNS): options under discussion, not yet decided.
- Backlog (2026-10-09): a richer Jellyfin overview in the hub, in the spirit of Tracearr's history:
  library counts (movies, series, episodes), what is pending or downloading (Jellyseerr, Sonarr,
  Radarr, the download clients), watch stats and a per-user leaderboard. Not planned into a
  milestone yet.

## 5. Non-goals

- No internet exposure, no login, no SSO (for now).
- No container control; Dockge does that.
- No trading, order entry or investment recommendations. The only writes to Ghostfolio are
  confirmed DEGIRO imports (M7).
