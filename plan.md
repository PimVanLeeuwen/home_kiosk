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
| Pi kiosk controls | Out of scope for now (dimming, rotation choice). Superseded 2026-10-09: three ESP32-P4 desk panels replace the Pi kiosk, with rotation, night hours and touch controls (M16). |
| Home control | Hue Bridge local API only, no cloud; Apple Home follows through the bridge (M17). |
| Music | Spotify Web API with the owner's Premium account; any device on the account (M18). |
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

**M1. Foundation**. **Done 2026-09-30.**
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

**M9. Repos** (added 2026-10-01). **Done 2026-10-01.**
- A "Code" sidebar group with a Repos page: tabs Mine (PimVanLeeuwen), Hubble
  (Hubble-Community-Cafe) and GEWIS (only repos with your pull requests or commits). Private repos
  included through read-only fine-grained tokens, one per owner.
- Per repo: description, language, stars and forks, visibility, last push, open pull requests and
  issues, CI state of the default branch, latest release. Archived repos hidden.
- One GraphQL query per owner every 30 minutes, cached; the last good list stays on errors.

**M10. GitHub mirror** (added 2026-10-04). **Done 2026-10-04.**
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

**M11. Message templates** (added 2026-10-04). **Done 2026-10-08.**
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

**M12. Backup hardening** (added 2026-10-08). **Done 2026-10-09.**
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
  Changed 2026-10-13: CouchDB, Jellyfin (`jellyfin` and `jellyfin-public`) and Uptime Kuma
  (`status`) may be public; Tandoor is reached over Tailscale only, and the UGOS admin (`nas`)
  and the unused `rss` record are taken off the internet.
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
  for attribution, so the tile names it. The kiosk slide moves to the desk panels' Now panel (M16).
- The hub as a real PWA, replacing today's plain "Add to Home Screen" bookmark: a web app
  manifest (`display: standalone`, name, icons, theme colour), iOS safe-area padding, and a
  service worker that caches the app shell and the last API payloads, so the app opens offline
  and shows them as stale. No web push: alerts stay on Telegram. Installed from the Tailscale
  HTTPS address (`*.ts.net`): browsers only run service workers over HTTPS, so on the plain LAN
  address the hub works as before, without offline mode. The service worker leaves `/kiosk/`
  alone. The existing home screen icon has to be removed and added again from the ts.net
  address.

**M16. Desk panels** (added 2026-10-09; replaces the planned Pi kiosk)
- Hardware: three Waveshare ESP32-P4-WIFI6-Touch-LCD-4B (4", 720×720, 5-point touch, Wi-Fi 6 on
  2.4 GHz through an ESP32-C6, 5 V over USB-C or the back header). Ordered 2026-10-09, not
  arrived yet. The microphones stay off in the firmware; the speaker is unused.
- Research, links and shops: [docs/desk-panels.md](docs/desk-panels.md). Clickable mockup of
  the three panels: [docs/desk-panels-mockup.html](docs/desk-panels-mockup.html) (open the file
  in a browser; it is not served by the hub).
- Design is a requirement, not polish (decided 2026-10-09): the panels are for information and
  for home, music and other control, and they must also be beautiful desk pieces. The three read
  as one object: same margins, header line and dot position. Each throws meaningful light: Now
  follows the sky, Home glows in the warm or cool white its lights have
  right now, or the album colours, House stays a
  quiet violet, an error turns all three red. Calm motion, a few large type sizes, nothing below
  24 px. Every screen is checked on a real panel (photos) before it ships, not only in tests.
  Details in [docs/desk-panels.md](docs/desk-panels.md#design).
- Roles, editable in the hub (Settings → Desk panels): left **Now** (clock, weather, Buienradar
  rain, the morning train, calendar, the day view, headlines), middle **Home** (the living room's
  lights, its air and the Christmas plugs, M17; the Apple devices, M20; Now Playing while music plays, otherwise a music
  card with favourite playlists, M18; never rotates), right **House** (NAS, Money, Code, Jellyfin, backups, alerts). The screens
  beyond the basics are M20. Each panel rotates through its cards; a touch
  pauses its rotation for 60 seconds. An ERROR alert takes over all three until dismissed. Night
  hours: Now shows a dim clock, Home and House dim, Money is off.
- Firmware: one ESP-IDF + LVGL 9 build for all three; a panel only knows its name. It fetches
  its layout and data from `/api/desk/<name>` (every payload with `as_of` and `stale`; stale
  cards are dimmed with their age). Built in GitHub Actions, updated over Wi-Fi from the hub, no
  cloud. The Wi-Fi password is a build secret, never in the repo.
- Writes from a panel (mute, lights, music) use a per-panel device key created in the hub, since
  `same_origin_json` only protects browsers. Keys can be revoked in Settings.
- Heartbeat: the hub alerts when a panel has not polled for 10 minutes.
- Stand. Nothing ordered yet; first test the angles with three cheap phone stands.
  - Requirements: about 15° tilted back, the outer panels turned 12 to 15° in, 8 to 10 mm
    gaps, one row of about 30 cm below the monitor. Heavy enough not to slide or tip when
    the panels are touched (wood, a steel weight or a weighted print, rubber feet). Room
    behind each board for its components and the USB-C port, and a cable channel.
  - Before designing: measure one board (depth, mounting holes, USB-C position). Waveshare
    gives only the outline (86.5 × 86.5 mm, display 71.93 × 71.93 mm).
  - Options: a ready-made single-panel stand for this board on MakerWorld (print three; not
    checked for fit); a parametric OpenSCAD stand for all three, written in this repo
    (angles and gaps as parameters), printed by a friend, a print service or TU/e's maker
    facilities, possibly split in two for a small printer; the same design laser-cut as
    stacked plywood or acrylic (for example Snijlab), exported to 2D from the model; or an
    oak or walnut block (about 30 × 6 × 4.5 cm) with three angled pockets from a carpenter
    or a CNC router. Preferred: the OpenSCAD model, then print or laser-cut.
- Power. Nothing ordered yet. Each board takes 5 V, over USB-C or the 5 V and GND pins on its
  back header.
  - Preferred: one cable to the stand. A USB-C PD trigger board set to 5 V, or a 5 V 4 A
    supply, feeds a 5 V line inside the stand that powers each board through its header pins.
    Measure one board's draw at full brightness first (expected around 2 W, not verified)
    and size the supply with headroom for three.
  - Fallback: three short USB-C cables to a 3-port USB charger behind the monitor.
  - Not used: the Ethernet variant (ESP32-P4-86-Panel-ETH-2RO, 6 to 30 V); a wired network
    needs a switch on the desk and only suits a wall mount.
- Order of work: test one board on a phone stand and settle the angles, measure it, write the
  OpenSCAD model, choose print or laser-cut, then buy the power parts.
- The 720×1280 `/kiosk/` carousel retires once the panels run.

**M17. Home control** (added 2026-10-09)
- The hub talks to the Hue Bridge's local CLIP v2 API with an application key (created once with
  the bridge's link button, kept in `.env`). No Hue cloud. The bridge's event stream keeps the
  hub's state live, so changes from the Home app, Siri or a switch show at once.
- Everything in the house is Hue (lights and smart plugs), so Apple Home follows on its own: it
  reads the same bridge. Non-Hue HomeKit devices would need Home Assistant; there are none now.
- The panel controls only the room the desk is in (decided 2026-10-10): the living room with its
  open kitchen. Its lights: 3 White Ambiance GU10 spots in the kitchen part (warm to cool white,
  no colour) and 2 white bulbs (brightness only). Other rooms are never controlled from the desk.
- Home panel, first card: a tile for the kitchen spots and one for the lamps (tap on/off, hold
  and drag for brightness), each glowing in the white it has now; five warm-to-cool swatches for
  the kitchen spots. (A scenes card was dropped on 2026-10-10: it would not be used.)
- Second card: **Air** in the living room: the temperature large, humidity, PM2.5, CO₂ as a ring
  (Fresh below 800 ppm, Getting stuffy to 1200, Open a window above) with the outside
  temperature from Buienradar beside it, and CO₂ over the last 8 hours. Needs a sensor; the ALPSTUGA (option 1) is
  ordered:
  1. **IKEA ALPSTUGA**, EUR 29.99 at IKEA NL: CO₂, PM2.5, temperature, humidity (no VOC).
     Matter over Thread, so it needs a Thread border router (an Apple TV 4K or HomePod mini in
     Apple Home is one) and then shows in Apple Home too. For the hub to read it, a Matter
     controller runs on the NAS (the open-source matter-server in Docker), added as a second
     controller from Apple Home. Cheapest, but the most moving parts, and reviews call its
     sensors noisier than dedicated monitors.
  2. **AirGradient ONE**, about EUR 290 at EU resellers (USD 230 direct): CO₂, PM, TVOC, NOx,
     temperature, humidity, open source, with a local HTTP API the collector reads directly
     over Wi-Fi. Simplest to connect and the most accurate.
  3. **Apollo AIR-1** (ESPHome), EUR 130 without CO₂ to EUR 208 with CO₂ and gas at Domadoo;
     EU distributor SlimHuisje.nl. Local ESPHome API.
  The Hue motion sensor only gives temperature. Recommended (2026-10-10): option 1, the
  ALPSTUGA. The house has two Apple TVs and several HomePods, which are Thread border routers
  already, so it joins Apple Home directly; the hub reads it through matter-server on the NAS
  (host network, IPv6 on the LAN). Ordered, not arrived yet (2026-10-12).
- The Hue plugs are used for Christmas decorations: their switches only show in the season
  (dates set in Settings).
- No light strips for now (2026-10-10). If ever: Hue's own strip is the only one that also shows
  in Apple Home; cheaper Zigbee strips (Innr Flex Light Colour, about EUR 44 for 2 m and EUR 70
  for 4 m at Amazon.nl and GAMMA; Gledopto controllers plus any strip; Lidl Livarno when in
  stock) work with the Hue Bridge and this hub, but not in Apple Home or Hue Entertainment.
- A Lights page in the hub with the same controls.
- A new deliberate write (decided 2026-10-09): lights, plugs and scenes on the Hue Bridge.

**M18. Music** (added 2026-10-09)
- Spotify Web API with the owner's Premium account: a developer app in development mode (owner
  must keep Premium; up to 5 users). Logged in once through the hub; the redirect URI is the
  hub's Tailscale HTTPS address. The refresh token stays on the NAS.
- Shows what plays on any device on the account (phone, Mac, speakers, AirPlay from the phone),
  podcasts included. Polled every 3 seconds while playing, slower when idle; the panel moves the
  progress bar between polls. Album art is fetched by the hub, so panels never contact Spotify.
- When nothing plays, Home's last card is Music: four favourite playlists as large covers with a
  play button, to start from the desk on the last used device (tap the device to change it),
  and what played last.
- Now Playing on the Home panel (moved from Now, 2026-10-10; redesigned 2026-10-12): the cover
  with a record sliding out behind it that spins while music plays (the album art as its label),
  an equaliser that moves with playback, a progress line with a glowing thumb and a play button
  lit in the album's colour, on a blurred art background;
  title, artist, progress, previous / play-pause / next, volume, and the device name (tap to
  move playback). When music starts it becomes Home's first card and the panel shows it; Home
  never rotates, so it stays there until you swipe to the lights. Two minutes after a pause the
  card goes and the lights are back.
- A new deliberate write (decided 2026-10-09): Spotify playback control.

**M19. Desk PC power** (parked 2026-10-10)
- Left out for now (decided 2026-10-10): there is no ready-made option that works locally out of
  the box, and the owner does not want to build one. The research is kept under Open items, in
  case a ready-made product turns up.

**M20. Panel screens** (added 2026-10-10)
- **Your train** (Now, weekday mornings): the owner takes the direct 07:16 from Leiden
  Centraal to Rotterdam Centraal every weekday. The collector follows that departure with
  the NS API (free key from the NS API portal, in `.env`) from about 06:00 until it leaves:
  cancelled, delayed, platform change, disruptions on the route. Decided 2026-10-10: every
  weekday; Telegram only for problems (no "on time" message); these messages skip quiet hours.
  The card must not read as a clock: the time sits in a labelled "Departure" box, the status
  (On time, 6 min late, Cancelled) is the large line, then "Leaves in 34 min from platform 3",
  or the next direct train when it is cancelled.
  Decided 2026-10-13: also checked the evening before each weekday (20:00 and 22:00), so a
  cancellation is known in time to set an earlier alarm; Telegram only for problems, and a
  problem sent in the evening is not sent again in the morning. In the hub: a card on Home on
  weekday mornings until the train has left, and in the evening only when tomorrow's train has a
  problem (mockup `docs/hub-train-mockup.html`). Built 2026-10-14 (collector): `/api/train` from
  NS's trips, journey (the stations it passes, for matching disruptions: a disruption counts when
  its stretch covers two or more of them) and disruptions; a `train` alert rule (late from 3 min
  and again at 10, 15, 20, 30, 45, 60; cancelled with the next direct train; skipped stops; a
  track change; works or a disruption on the route), routed as its own category "Your train".
- **Clock and Your day** (Now, redesigned 2026-10-12): the clock sits inside a ring of the next
  two hours of Buienradar rain in 5-minute segments, starting at the top at now and going round
  clockwise, segment length by intensity, with "Rain 07:11 to 07:56, peak 2,8 mm/u" below. The
  day view lays the sun's arc over a sky band that runs from night through dawn, day and dusk,
  above the temperature curve and the chance of rain.
- **Laundry** (Home, added 2026-10-12): the washer and dryer (ConnectLife app) as two portholes:
  water turning inside while a machine runs, a ring counting down, the program and when it will
  be ready; a finished machine glows green with "Take it out". No Telegram message (decided
  2026-10-12): the ConnectLife app already notifies; the card is for a glance now and then. Source: ConnectLife has no local API, only its cloud. The open-source `connectlife`
  Python library (used by the connectlife-ha integration) logs in with the app account; the
  collector polls it about once a minute, read-only, with the account in `.env`. It is
  unofficial and can break when ConnectLife changes its API or terms. Decided 2026-10-12: both machines
  are Hisense; the card only shows while a machine runs or is done (then it is gone until the
  next run, after the door has been opened if ConnectLife reports it, otherwise after a tap on
  "Taken out" or two hours). The models are a WF5S1043BW washer and a DH3S802BW2 dryer. They
  are not in connectlife-ha's device list, but their siblings are, with the same device type
  codes: the WF5S1045BW washer (type 025) and the DH3S802BW3 dryer (type 030). So support is
  likely; the property mapping may need the two models added. ConnectLife also publishes its own Home Assistant plugin for Hisense
  appliances (Connectlife-LLC/HomeAssistantPlugin), a second reference for the API.
- **Calendar** (Now): today's events only. Design (2026-10-10): the next event large with a ring
  counting down to it in its calendar's colour, the day from 07:00 to 23:00 as a ribbon of
  coloured blocks with a glowing now line, then the later events. Read-only, no
  reminders, no bin days. Decided 2026-10-10: CalDAV to `caldav.icloud.com` with an
  app-specific password from the Apple account page, kept in `.env` (it also opens iCloud mail
  and contacts, so NAS-only, revocable any time). All calendars are in Apple Calendar. Settings
  → Desk panels lists them with their colours and a switch each, so some never show; events
  from the chosen ones show with their full titles.
- **Headlines** (Now): the top stories from the News reader (M6): the lead story full-bleed over
  its image (proxied by the hub) with the source as a badge, then two more with thumbnails; tap
  one to save it to Readeck, and its bookmark fills.
- **Code** (House): 16 weeks of commit activity as a grid, then the CI state of the default
  branches and running pull requests from the Repos data (M9); a failing build stands out.
- **Media** (House; refocused 2026-10-12): not what is being watched (the owner knows), but what
  needs attention: what is downloading (poster, episode or movie, size, an animated progress bar,
  percentage and time left, from the Sonarr and Radarr queues and the download clients) and
  missing episodes (aired but not downloaded, from Sonarr's wanted list, with how long ago and
  whether it is still searching), plus the next episode to air. Posters are fetched and resized
  by the hub. Shares its data with the backlog's richer Jellyfin overview in the hub.
  Built 2026-10-14 (collector and hub): `/api/media` every minute from Sonarr's and Radarr's
  queues, Sonarr's wanted list and its calendar for the coming week, with the keys the service
  tiles already use; one app down leaves the other's part. Posters through the hub
  (`/api/media/posters/…`, the apps' own 250-pixel versions, only for items in the current
  answer). In the hub a Media page under House (mockup `docs/hub-media-mockup.html`).
- **Top movers** (House, Money; redesigned 2026-10-12): a heat map of the holdings, each tile
  sized by its share of the portfolio and tinted green or red by today's move, with the ticker,
  the change and the name (type scales with the tile; the name is left out on the smallest);
  the S&P 500, Nasdaq 100 and AEX below.
- **My sites** (House, added 2026-10-10): the owner's own sites: example.com,
  aoc.example.com, hubble.cafe, meteor.cafe, admin.hubble.cafe, harry.hubble.cafe and
  harry-admin.hubble.cafe. The list is grouped Personal and Hubble with short names (aoc, admin,
  harry, harry-admin); only a percentage below 100% is shown.
  Design: one ring per site, split into 30 day-segments from 30 days ago round to today; healthy
  days a quiet green, a blip amber and an outage red with a soft glow, so incidents stand out;
  the count of sites up in the centre and a list with each site's uptime beside it.
  Source (decided 2026-10-10): Uptime Kuma, already running, with an HTTP monitor per site and a
  second status page that the collector reads. Kuma already sends a Telegram message through the
  hub when a site goes down. The collector keeps its own daily up, blip or down record per site
  in SQLite from Kuma's heartbeats, so the 30 days do not depend on how much history Kuma's
  status page returns. These checks run on the NAS, so they cannot report the NAS itself being
  down (see the Hetzner VPS open item).
- **Services** (House, added 2026-10-10): only outside services something here depends on
  (kept short on purpose, 2026-10-10): GitHub (code, CI, image builds, the mirror), Cloudflare
  (DNS and the tunnel for the public sites), Docker Hub (the hub's images and Watchtower's pulls),
  Tailscale (remote access, the exposure scan), Hetzner (the Storage Box backups and the Docker
  server the Hubble sites run on), TransIP (DNS for the Hubble sites) and Proton (mail). Not listed: Spotify, Telegram and iCloud, whose own cards go stale when they fail. Read from their public status pages (most use Statuspage's `/api/v2/summary.json`),
  every 5 minutes by the collector, never by the panels. Decided 2026-10-12: only the components
  the house uses count (Cloudflare's headline status nearly always reports a far-away colo),
  listed in config.yaml; Hetzner has no API, so the collector reads the data its status page
  embeds, and counts only the Storage Box, Cloud Server and the German locations; TransIP's
  TransNOC is plain HTML and counts as fine only while it says all services are available;
  maintenance shows only while it runs; an incident sends a Telegram warning when it starts and
  when it is resolved. Served at `/api/outside-services`, with a Home tile and a section on the
  Services page in the hub. Each service shows its own logo (Simple
  Icons, CC0, bundled with the hub and converted for the panels, never loaded from a CDN; TransIP
  has none there, so it gets a letter tile), on a dark glass tile with a glow in its brand colour.
  When all is well: the services as a ring around a glowing check. During an incident: a card with the service, its state
  and how long it has run, the incident's timeline (Investigating, Identified, Resolved) and a
  softly pulsing halo; the other services as a row of small icons below.
- **Apple devices** (Home, moved from House 2026-10-10): the two Apple TVs and the HomePods,
  each with whether it is online, and what it plays. Design (2026-10-12): a lit floor plan;
  rooms are outlined zones, and a room where something plays glows in that colour; each device
  is a luminous orb with a halo, playing ones sending out ripples; small pulses of light travel
  along the Thread mesh between them, and a link to an offline device turns into a broken amber
  line with the device dashed in amber; the air sensor sits on the mesh. Below the plan a
  now-playing bar with a thumbnail, the title, the room and a moving equaliser. Room positions are set once in Settings.
  The devices (2026-10-10): living room, an Apple TV and two big HomePods as a stereo pair (shown
  as one group with the TV, as they play its sound); bedroom, an Apple TV and a HomePod mini;
  bathroom, a HomePod mini. To check when building: which are Thread border routers (the
  HomePod mini and HomePod 2nd generation are; the Apple TV 4K Wi-Fi-only 64 GB model and the
  first HomePod are not). Possible locally: every device announces itself on
  the LAN over Bonjour (mDNS), so the hub sees which are online; Thread border routers announce
  `_meshcop._udp`, so it can show whether Thread (which the air sensor needs) is up; pyatv
  (open source) reads what an Apple TV plays after a one-time pairing, and HomePods report
  what they play over AirPlay. Not possible: firmware updates, which device is the active home
  hub, or anything else inside Apple Home. Bonjour is multicast, so the collector needs the
  host network or a small host-network helper; the collector container is on a bridge network
  today. Device names to fill in; the mockup uses examples. An Apple TV or HomePod going
  offline for 10 minutes is a warning.
- **NAS, Backups, Alerts and the train**, redesigned again 2026-10-10 to be desk pieces:
  - NAS: an instrument-style arc gauge for the fullest volume (ticks, a glow, a red mark where
    it would alert), its size and runway below, then tiles for CPU and memory with live
    sparklines and one for the disks (a glowing dot per disk) and the UPS.
  - Backups: a verified seal with last night's time, duration and size and the last verified
    restore, a NAS to Hetzner (encrypted) line with a gentle moving light, and the last 30 nights
    as bars (a slow night in amber, last night bright).
  - Alerts: an open alert gets a large pulsing icon, the severity, a big title, how long it has
    been open and when Telegram was told, and a bar with the warning and error thresholds; All
    quiet gets slow ripples round a check, how long it has been quiet and a dot per day of the
    week (amber on days that had an alert).
  - Train: the departure box and the status word, a ring counting down to departure (or the
    next train when cancelled), and the route with its stops and times (Leiden Centraal,
    Den Haag HS, Delft, Rotterdam Centraal); a delay moves the times.
    The mockup's stop times are examples; the real ones come from the NS API.
- **Scenes, Portfolio and Alerts** (redesigned 2026-10-10): each scene tile is lit in the colours
  of its lights, with a dot per light and the active scene marked; Portfolio has a day, week,
  month and year switch, its line green or red with the change for that period, and since
  2026-10-12 the chart runs edge to edge with a glowing line and the period's high; Alerts shows a
  calm "All quiet" with a check when nothing is open, instead of an empty list.
- No ambient mode (dropped 2026-10-10): the panels always show these screens; an idle art mode
  would defeat their purpose.
- Each screen follows the design bar in M16 and is checked on a real panel.

Order: M1, M2, M3 + M4, M5, M6, M7, M8. M9 slotted in after M2, M10 after M8, then M11. Then
M12, M13, M14, M15, M16, M17, M18, M20 (M19 parked).

## 4. Open items

- The Pi kiosk is replaced by the desk panels (M16, decided 2026-10-09). Until they run, the
  carousel stays at `/kiosk/` (`?data=api` for live data; `/kiosk` and `/read.html` redirect).
- Password manager (discussed 2026-10-09, not decided): no self-hosting (Vaultwarden was
  considered and dropped: the vault would hold the passwords needed to rebuild the NAS).
  Compared Bitwarden and NordPass; recommended Bitwarden in the EU region (open source, yearly
  published audits, a CLI, a later move to Vaultwarden without new apps), Families if shared
  with the household, otherwise Premium. NordPass mainly wins on price, for example in a bundle
  with NordVPN. Either way: a paper emergency sheet away from the NAS (master password, 2FA
  recovery codes for Tailscale, Hetzner and GitHub, the rclone crypt passwords, the LiveSync
  passphrase) and 2FA for Tailscale and Hetzner on a passkey, not only a TOTP in the vault.
- Ad and tracker blocking (DNS), not decided. Software: AdGuard Home (UI, encrypted upstream,
  per-device rules), Pi-hole, Blocky (one config file, easy to run twice, Prometheus metrics),
  Technitium, or hosted NextDNS (nothing to run, but it sees every lookup). Upstream: Quad9 or
  Mullvad over DoH/DoT, or Unbound resolving itself. Handed out by the router (whole house) or
  Tailscale DNS (devices anywhere); one instance on the NAS means no DNS when the NAS is down,
  so run two (NAS plus a VPS or the router). iCloud Private Relay and browser DoH bypass it.
  Proposed: AdGuard Home on the NAS and a second box, and a "blocked today" tile. Open
  question: which router (some can run AdGuard themselves).
- Hetzner VPS next to the NAS (discussed 2026-10-08, not decided; the exposure scan went to a
  GitHub workflow instead). A small cloud server (CX22 or CAX11, about EUR 4 to 5 a month) on the
  tailnet could be: an outside uptime watcher that also notices the NAS losing power or
  internet; a weekly restore drill into throwaway containers; an append-only restic
  `rest-server`, so a compromised NAS cannot delete backups; a Caddy proxy replacing cloudflared
  so Cloudflare no longer sees the traffic (but one more public box to maintain); an exit node
  and second DNS. SSH over Tailscale only, unattended-upgrades, compose files in a `hetzner/`
  folder in nas-docker. Not worth it: Headscale, media or Immich on the VPS.
- Backlog (2026-10-12): Tailscale status and the connected devices, with their names and
  addresses, first as a desk panel screen, then as a page in the hub (phone first). Source: the
  collector already reads tailscaled's LocalAPI (`GET /localapi/v0/status`, read-only) for the
  NAS's own name; the same answer lists every peer (host and MagicDNS name, Tailscale IPs, OS,
  online, last seen, direct or relay, exit node, traffic) and tailscaled's health warnings, so no
  key or cloud is needed. Designed 2026-10-12: a Tailnet card on the House panel (the NAS in the
  middle, every device around it, a running line for a direct connection and a dashed violet one
  through a relay, the online devices listed below; `docs/desk-panels-mockup.html`) and a
  Tailscale page under House (the same map, the NAS's names and addresses, every device as a tile
  that opens for its details; `docs/hub-tailscale-mockup.html`). The warning state is
  tailscaled's own health warnings, not key expiry: keys do not expire on this tailnet (M13).
- Backlog (2026-10-09): a richer Jellyfin overview in the hub, in the spirit of Tracearr's history:
  library counts (movies, series, episodes), what is pending or downloading (Jellyseerr, Sonarr,
  Radarr, the download clients), watch stats and a per-user leaderboard. Not planned into a
  milestone yet.
- Backlog, ideas not yet chosen (2026-10-08): dynamic energy prices for today and tomorrow
  (EnergyZero, no key), an Immich "on this day" photo, a command palette (Cmd-K) for services,
  pages and repos, and a morning digest in Telegram (overnight updates, backup, disk, weather).
  Desk panels: house and productivity widgets and actions, later. (The calendar and the morning
  train moved to M20; there are no bin days to show.)
- Desk panel screen ideas (2026-10-10). Chosen into M20 on 2026-10-10: calendar, the morning
  train (instead of general departures), Jellyfin, code and headlines (ambient was chosen,
  then dropped). Not chosen yet:
  1. Ride: the next dry window to cycle (from Buienradar).
  2. Focus: one tap starts a 50-minute ring timer, the lights go to a Focus scene, a
     focus playlist starts and Telegram alerts are held until the end.
  3. Memories: an Immich "on this day" photo, full-bleed, LAN only, off at night.
  4. Air: outdoor air quality at home from Luchtmeetnet (RIVM), with pollen if a free
     source exists.
  5. Timers: tea or kitchen timers that chime on a panel's speaker (a speaker is not fitted
     yet).
- Desk PC power (parked 2026-10-10, was M19): turn the Wi-Fi desk PC on from the Home panel.
  Wake-on-WLAN mostly only wakes from sleep; a Hue plug with "Restore on AC power loss" can boot
  it but cannot shut it down and must never cut a running PC. What works is an ESP on the
  power-button header, running ESPHome: the nearest to ready-made is the Sinilink XY-WPCE
  (an ESP8266 PCIe card, about EUR 10 to 15 on AliExpress, cloud firmware until flashed with
  ESPHome over 1 mm serial pads, https://devices.esphome.io/devices/sinilink-xy-wpce/), or a DIY
  ESP32-C3 SuperMini with a PC817 optocoupler, powered from the motherboard's USB 2.0 header
  with ErP off (designs: pixelwave Wake-On-ESP32, Erriez ESPHomePCPowerControlHomeAssistant).
  Tuya and eWeLink PCIe cards on Amazon need a cloud app. Revisit if a local ready-made card
  appears.
- Considered and dropped (2026-10-08 and 09): a Docker socket proxy; pinned image versions
  with Renovate PRs (updates stay automatic, no PRs); a rollback command from the previous image
  digest; a Tailscale key expiry rule (keys do not expire on this tailnet); a privacy blur for
  amounts on the kiosk; Tailscale identity headers to gate writes; self-hosting a password
  manager. Watchtower: containrrr/watchtower was archived on 2025-12-17 (forks such as
  `nickfedor/watchtower`, or What's Up Docker); the owner parked this on 2026-10-09.

## 5. Non-goals

- No internet exposure, no login, no SSO (for now).
- No container control; Dockge does that.
- No trading, order entry or investment recommendations. The only writes to Ghostfolio are
  confirmed DEGIRO imports (M7).
- No microphone or voice control on the desk panels.
