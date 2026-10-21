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
  card with favourite playlists, M18; since 2026-10-21 it rotates unless music plays or every light
  is off), right **House** (NAS, Money, Code, Jellyfin, backups, alerts). The screens
  beyond the basics are M20. Each panel rotates through its cards; a touch
  pauses its rotation for 60 seconds. An ERROR alert takes over all three until dismissed. Night
  hours: Now shows a dim clock, Home and House dim, Money is off.
- Firmware: one ESP-IDF + LVGL 9 build for all three; a panel only knows its name. It fetches
  its layout and data from `/api/desk/<name>` (every payload with `as_of` and `stale`; stale
  cards are dimmed with their age). Built in GitHub Actions, updated over Wi-Fi from the hub, no
  cloud. The Wi-Fi password is a build secret, never in the repo.
- Writes from a panel (mute, lights, music) use a per-panel device key created in the hub, since
  `same_origin_json` only protects browsers. Keys can be revoked in Settings. Built 2026-10-19 (decided
  2026-10-19: the hub hands the key over once, no pairing code): a board gets a key when it is
  given a panel; the hub hands it over in the board's next answer and then keeps only its
  SHA-256; the board keeps it in its own storage and sends it as a Bearer token. Changed
  2026-10-21 (a missed handover left boards with the wrong key, every tap a 401): the hub repeats
  the key in its answers until the board sends it back, with its polls or its first write, and
  keys that were handed over once but never confirmed are issued again. Taking the panel
  away or forgetting the board revokes it; Settings, Desk panels shows each key (none, on its
  way, in use) with New key and Revoke key. The first use: a tap on a headline saves it to Readeck
  (`POST /api/desk/save` with the article id; the hub looks up the link and remembers what was
  saved, so the bookmark stays filled; decided: a second tap does nothing).
- Heartbeat: the hub alerts when a panel has not polled for 10 minutes. Built 2026-10-19: the
  "Desk panels" alert rule (on by default, the minutes adjustable on the Alerts page) warns once
  when a board with a panel has not asked the hub for that long, and says when it is back;
  boards without a panel (on the bench) are left alone.
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
- Stand: none yet (2026-10-19); look into the 3D-print option once the screens are further.
- Arrived 2026-10-19. Decided 2026-10-19: the firmware lives in `panels/` in this repo; built in
  `espressif/idf:v5.5.6` (Docker, as CI will), flashed with esptool 5.6.0 over the UART USB-C
  port; ESP-IDF v5.5; the Wi-Fi details are a build secret (`panels/firmware/sdkconfig.secrets`,
  git-ignored; a GitHub Actions secret in CI). Pinned components: Waveshare's board package
  `waveshare/esp32_p4_wifi6_touch_lcd_4b` 3.0.1, LVGL 9.3.0, `esp_lvgl_adapter` 0.6.3,
  `esp_hosted` 2.12.11, `esp_wifi_remote` 1.6.3 (`dependencies.lock` committed).
  Bring-up 2026-10-19 on the first board (MAC e8:f6:0a:e4:42:c8): an ESP32-P4 **v1.3** (Waveshare's
  defaults assume v3.x; v1.x builds use 200 MHz PSRAM and do not run on v3.x chips). All three
  boards checked the same day: v1.3 with 32 MB flash and PSRAM (MACs e8:f6:0a:e4:42:c8, :ac and
  :b0), and the same factory image; display, GT911 touch and Wi-Fi through the
  factory C6 image work (the C6 reports ESP-Hosted 0.0.0 against 2.12 on the P4: works, but
  ESP-Hosted warns about possible RPC timeouts; update the C6 only if Wi-Fi proves unreliable).
  The factory flash is backed up per board in `~/panel-backups/` (read in 2 MB pieces: one long
  read breaks off with serial noise). `/api/desk/{now,home,house,test}` answers as a stub. On the
  real screen the hub's dark `#101014` looks grey (IPS glow): panel screens use true black and a
  lower default brightness (since 2026-10-19: full brightness, the owner's choice; one board's
  backlight stayed off at 40 %). Next: the angles and the board's depth and USB-C position, then the real `/api/desk` layouts and screens.
  Built 2026-10-19 (telling the boards apart; decided 2026-10-19: chosen in the hub's Settings,
  not config.yaml): every board runs the same build and asks `/api/desk/board/<MAC>?firmware=<commit>`
  every 30 s with the chip's own MAC (as written on its back). The hub keeps each board's last
  visit and firmware (`desk_board`) and answers with its panel's screens; Settings, Desk panels
  lists the boards (online when seen in the last two minutes) and assigns Now, Home, House or
  Test, one board per panel, or forgets a board. A board without a panel shows "Which panel is
  this?" with its MAC, a panel without screens yet says so; a change reaches the board within
  30 s, without a restart. `/api/desk/<name>` still answers by name.
  Built 2026-10-19 (updates over Wi-Fi; decided 2026-10-19: CI builds the firmware into the
  dashboard image, installs only between 04:00 and 05:00, no signed images, the hub being LAN
  only): CI builds `panels/firmware` without Wi-Fi details (the Docker Hub images are public)
  and versions it with git's hash of that folder, so only firmware changes reach the boards. The
  hub serves `/panels/firmware.json` and `/panels/firmware.bin`. A board saves the network from
  its one USB flash in its own storage, checks every 10 minutes, downloads a different version
  into PSRAM and then writes its other app slot, and restarts; the bootloader keeps the old slot
  until the new firmware has reached the hub, and rolls back after 5 minutes without it (tested
  on the bench). `panels/tools/update.py` installs at once over the serial console. Making the
  1.7 MB download work needed two ESP-Hosted settings for the C6's old factory image: packet
  buffers in internal RAM (DMA from PSRAM refused unaligned 66-byte TCP acknowledgements) and
  the default streaming receive (the C6 sends several packets in one 3 kB transfer).
  Added 2026-10-19 at the owner's request: "Update to <version>" per board in Settings, Desk
  panels, when its firmware is not the one the hub offers (the page reads `/panels/firmware.json`
  itself); the request goes out once with the board's next answer, which installs at once (on
  the bench: 54 s from the press to the new firmware kept). The night window stays for the rest.
- **Start-up screen** (planned 2026-10-19, at the owner's request): after a restart (power, an
  update) a board now shows the empty clock ("--:--", blank header) for the 10 to 20 seconds
  until Wi-Fi is up and the hub has answered. Instead: a calm start-up screen in the panels'
  style, true black with the quiet violet light, a small animation that moves while it waits
  (pulsing dots or a slow arc, kept small: full-screen animations run at about 6 fps here), and
  one line on what it is doing ("Connecting to Wi-Fi", "Asking the hub"), then the dip through
  black into the first screen. When it takes long, it says so plainly ("Can't reach the hub at
  192.168.1.10", "No Wi-Fi network saved on this board") with the board's MAC, so a problem is
  readable from the desk. Mockup first, checked on a real panel.
  Built 2026-10-19 (decided: pulsing dots, a problem shown after 30 s): three violet dots
  brighten one after another under "Connecting to Wi-Fi", then "Asking the hub"; after 30 s an
  amber dot and "Can't join the Wi-Fi", "Can't reach the hub" (with its address) or "The hub is
  not ready" (with its answer), and "No Wi-Fi network saved" at once. The MAC sits at the bottom.
  It is shown only until the hub's first answer: later outages keep the screens, marked stale.
- **Home panel frame and dimming** (built 2026-10-21): Home does not rotate. It is swiped left
  and right, shows dots for its screens, goes back to its first screen after a minute without a
  touch, and jumps to Now Playing when music starts. Its screens in order: Now Playing (while
  something plays), Lights, Laundry (while a machine runs or is done), Apple devices, Music. The
  hub's answer says `rotate` per panel and `dim` when every living room light is off (owner's
  request 2026-10-20); then all panels darken through a black layer over the screen, turned with
  the same dip through black as a screen change. Changed 2026-10-21 (owner's request): Home
  rotates like the other panels while nothing plays; while music plays it stays on Now Playing
  (even with the lights off); with nothing playing and every light off it lists only the light
  controls (`home_rules` in `app/desk.py`). A paused song counts as nothing playing. The
  backlight stays at full: one board's
  backlight went dark at 40 %, so lowering it is left to test together. LVGL allocates in PSRAM
  (`main/lvgl_memory.c`): with the C library's malloc its small objects took internal RAM, and
  with Home's five screens only 17 kB was left and the Wi-Fi buffers failed at start-up (now
  about 90 kB free).

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
  temperature from Buienradar beside it, and CO₂ over the last 8 hours. Designed 2026-10-21 (mockup
  in the session, approved): on the Home panel, the second card after the lights, the
  temperature large on the left with humidity and PM2.5 (µg/m³) below it and the sensor's own
  verdict small under PM2.5; on the right the CO₂ ring (400 to 2000 ppm, ticks at 800 and 1200,
  coloured green, amber or red by the words, the word under it); below, the CO₂ curve of the
  last 8 hours with dashed lines at 800 and 1200; the header "LIVING ROOM · AIR" and the
  outside temperature. Decided 2026-10-21: nothing extra above 1200 ppm (no jump to the card, no
  Telegram), the card just turns red in the rotation; in the hub, a card on Home beside Weather
  and Laundry. Built 2026-10-21 (hub, then panel): the hub's Air card (`AirCard`), and the
  Home panel's Air screen after the lights (`air_screen` in `app/desk_home.py`,
  `screen_air.c`; the CO₂ curve painted into a canvas). The panel font has no µ or ³, so the
  panel says "PM2.5 fine dust" where the hub says "µg/m³"; the clock font gained "," and "°"
  for the temperature. Needs a sensor; the ALPSTUGA (option 1) is
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
  (host network, IPv6 on the LAN). Ordered 2026-10-12; arrived 2026-10-21.
  Set up 2026-10-21: in Apple Home over Thread, then shared as a second Matter controller to the
  `matter` stack in nas-docker. Decided 2026-10-21: the Open Home Foundation's matter.js server
  (`ghcr.io/matter-js/matterjs-server:stable`), as python-matter-server is archived; same
  WebSocket API. The NAS needed `accept_ra_rt_info_max_plen = 64` on eth0 to take the Thread
  route from the Apple border routers, and a longer conntrack UDP timeout for the sleepy sensor
  (nas-docker README, Matter). Built 2026-10-21 (collector): `/api/air` from the Matter server
  every minute (`get_node`, read-only; `air` in config.yaml): temperature, humidity, CO₂,
  PM2.5, the sensor's own verdict, the CO₂ words, the outside temperature, and CO₂ every 5
  minutes for the last 8 hours. Decided 2026-10-21: no HomePod temperatures (Apple exposes
  them only inside the Home app).
- The Hue plugs are used for Christmas decorations: their switches only show in the season
  (dates set in Settings).
- No light strips for now (2026-10-10). If ever: Hue's own strip is the only one that also shows
  in Apple Home; cheaper Zigbee strips (Innr Flex Light Colour, about EUR 44 for 2 m and EUR 70
  for 4 m at Amazon.nl and GAMMA; Gledopto controllers plus any strip; Lidl Livarno when in
  stock) work with the Hue Bridge and this hub, but not in Apple Home or Hue Entertainment.
- A Lights page in the hub with the same controls.
  Decided 2026-10-14: a Lights page only (no Home card), under a new Home group in the menu; the
  living room only; live from the bridge's event stream; the Christmas plugs as a later step
  (none are paired on the bridge now). Mockup `docs/hub-lights-mockup.html`.
  Built 2026-10-14 (collector): `hue` in config.yaml (the bridge at its reserved address
  192.168.1.20, its id, the key from HUE_APPLICATION_KEY, the two groups by light name: Kitchen
  spots = Keuken 1 to 3, Hue ambiance, 2200 to 6500 K; Ceiling lamps = Plafondlamp Bank and Tafel,
  filament). The bridge's certificate must chain to Signify's roots (`hue_ca.pem`, from openHAB,
  checked against the bridge) and name the bridge id. A full read every minute, the event stream
  in between; `GET /api/lights`, `PUT /api/lights/{group}` (on, brightness 1 to 100, one of the
  five whites) and `POST /api/lights/room` (all on or off), both same-origin writes that answer
  with what the bridge then reports; only the configured lights are ever touched.
  Built 2026-10-14 (hub): a Lights page right under Home in the menu (on a phone under More):
  per group a tile that glows in its current white, the top as the on/off button, a brightness
  slider sent once it rests (300 ms), five whites for the spots, a chip per light (unreachable in
  amber), "All off" or "All on" for the room; it asks the hub every 2 s and shows the bridge's
  answer to each change; while the bridge is away the last known state with the controls off.
  Built 2026-10-21 (Home panel): the Lights screen, a tile per group glowing in its white (tap
  switches it, hold opens a brightness slider sent when released), the five whites for the
  kitchen spots and "Switch all off/on"; the panel writes with its device key
  (`POST /api/desk/lights/{group}` and `/api/desk/lights/room`) and draws the hub's answer at once.
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
  move playback). When music starts it becomes Home's first card and the panel shows it; while
  it plays Home does not rotate, so it stays there until you swipe to the lights. Two minutes after a pause the
  card goes and the lights are back.
- A new deliberate write (decided 2026-10-09): Spotify playback control.
  Decided 2026-10-18: a Music page under Home and Lights, and a Now Playing card on Home while
  something plays (gone two minutes after a pause); four favourites chosen in Settings → Music;
  Spotify asked only while someone looks (at most every 2 s, nothing kept about what played);
  PKCE sign-in with only the Client ID (SPOTIFY_CLIENT_ID), the refresh token in the hub's
  database. A favourite starts on the device that is already playing, otherwise on the living
  room Apple TV, which the hub wakes and opens Spotify on when Spotify does not list it (pyatv
  Companion, a one-time PIN pairing). HomePods are not Spotify Connect devices: AirPlay to them
  shows as the phone or Mac it comes from. Mockup `docs/hub-music-mockup.html`.
  Built 2026-10-18 (collector): `/api/music` (what plays with its cover and main colour, the
  devices, the favourites, what played last), `/api/music/login` and `/callback` (PKCE),
  controls (play, pause, next, previous, volume, transfer), playlists and favourites, covers
  through the hub as 300 px WebP (only Spotify's image hosts); writes same-origin only; a failing
  Spotify serves the last answer stale.
  Built 2026-10-18 (Apple TV wake): `music.wake` in config.yaml (the living room Apple TV's
  address, Companion credentials from APPLE_TV_LIVING_ROOM_COMPANION after a one-time PIN
  pairing). When a favourite should start there and Spotify does not list it, the hub switches it
  on and opens the Spotify app (`com.spotify.client`), then waits up to 15 s for Spotify to list
  it. Nothing else is sent to the TV.
  Built 2026-10-19 (hub): a Music page right under Lights (Now Playing with the record and the
  cover's colour, play, pause, previous, next and volume, the Spotify devices to move playback to,
  the four favourites), a Now Playing card on Home after Today while something plays (asks every
  5 s, gone two minutes after a pause), and Settings → Music (connect or disconnect, tick four
  favourites in order). Spotify names every Apple TV "Apple TV": the hub learns the living
  room's id while it is the only one listed, and shows it as "Apple TV Living Room".
  Built 2026-10-21 (Home panel): Now Playing (the cover on its record in the cover's colour, the
  device, a progress bar moved on between answers, previous, play-pause and next) first while
  something plays, and Music last (the four favourites as cover tiles, a tap starts one, and what
  played last). Covers come from the hub as small baseline JPEGs (`/api/desk/cover/{key}/{size}`)
  made from the WebPs it stored; the panel writes through `POST /api/desk/music/{action}` and
  `/api/desk/music/favourite/{n}` with its device key.

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
  Built 2026-10-19 (panel): the Now panel's train screen, between the clock and the day view,
  shown exactly when Home shows the card. As in the panel mockup: the departure in a labelled box
  (struck through when it does not run, the new time beside the old one when late), the status
  large in green, amber or red, "Leaves in 34 min from platform 3" with the platform as a pill
  (amber, the old one struck through, when it changed), a ring emptying over the last hour in the
  status colour with its light behind it, and the route with its times; when cancelled, the next
  direct train; the evening before, tomorrow's problem and the works on the route. The hub words
  everything (`app/desk_train.py`, kept to the Latin-1 the panel fonts hold); the panel counts
  the minutes down on its own clock.
- **Clock and Your day** (Now, redesigned 2026-10-12): the clock sits inside a ring of the next
  two hours of Buienradar rain in 5-minute segments, starting at the top at now and going round
  clockwise, segment length by intensity, with "Rain 07:11 to 07:56, peak 2,8 mm/u" below. The
  day view lays the sun's arc over a sky band that runs from night through dawn, day and dusk,
  above the temperature curve and the chance of rain.
  Built 2026-10-12 (hub): Home's weather card shows the rain ring around the temperature and the
  sun's arc (`RainRing`, `SunArc`); the hub has no clock of its own.
  Built 2026-10-19 (panel, the first screen): `/api/desk/now` carries the hub's time (epoch and
  the Amsterdam offset; decided 2026-10-19: the panels take their clock from the hub and never
  contact the internet, as neither the router nor the NAS serves NTP) and the clock screen's
  values (place, date, temperature and Buienradar's Dutch description as on Home, 24 rain values,
  the rain sentence worded as on Home). The firmware draws the ring with LVGL arcs (colour by
  intensity, as LVGL arcs take no gradient) around the time in Instrument Sans (decided
  2026-10-19: bitmap fonts converted once from Google's OFL TTF, `panels/firmware/fonts`). The
  C6's old ESP-Hosted image dropped the SDIO link on a few-kB answer: plain receive mode at
  20 MHz is stable. `panels/tools/shot.py` takes exact screenshots over the serial console.
  Refined 2026-10-19 at the owner's request: the sky light from the top in the colour of the time
  of day (night deep blue, dawn rose, day violet, dusk warm: the Home glow's colours, stronger), a
  soft violet glow behind the time, the header in small spaced capitals, the temperature in white
  beside the softer description. The display runs in 24-bit colour (RGB888): in 16-bit the soft
  glows showed visible bands. The console runs at 921600 baud for the larger screenshots.
  Redesigned 2026-10-21 at the owner's request (the dry ring read as a spinner, the bottom was
  empty, the light ignored the weather, the words were half Dutch): no ring; on a dry day the time,
  the weather in English and "Dry until at least 12:01" sit together in the middle; when rain is
  due, the time moves up and the next two hours stand as bars along the bottom (now, +1 h, +2 h),
  with "Rain from 10:31, about 35 min" above them. The header shows the date and the next sunset
  or sunrise; the light from the top takes the hub's colour for the sky outside, from the sun
  times and the weather (`app/desk_clock.py`). Buienradar is credited on Home, not on the panel.
  Built 2026-10-19 (panel, the second screen): the day view from Open-Meteo (decided 2026-10-19:
  free, no key, open data under CC BY 4.0, credited on the screen; only the weather block's
  coordinates are sent), fetched every 30 minutes for today and tomorrow. `/api/desk/now` carries
  it ready to draw: today from 06:00 to midnight, tomorrow from 20:00, a two-part sentence (rain
  likely from 50 %, a chance of showers from 30 %, else the warmest hour), high and low, sunrise
  and sunset. The panel turns between the clock and the day view every 15 seconds (10 at first;
  longer at the owner's request, to read it); a touch holds the screen for a minute. The chart is drawn once per answer into a canvas: drawn
  live, LVGL repeated hundreds of shapes for every strip of every frame and stalled.
  Changed 2026-10-19 at the owner's request: the panels show their picture a quarter turn to the
  right, so the USB ports sit at the top in the printed cases (touch turned with it); the turn
  between screens dips through black with the backlight instead of a crossfade (decided
  2026-10-19: the crossfade ran at about 6 frames a second, as LVGL redrew and blended both
  whole screens per frame; the backlight dims in hardware, smoothly).
- **Laundry** (Home, added 2026-10-12): the washer and dryer (ConnectLife app) as two portholes:
  water turning inside while a machine runs, a ring counting down, the program and when it will
  be ready; a finished machine glows green with "Take it out". No Telegram message (decided
  2026-10-12): the ConnectLife app already notifies; the card is for a glance now and then. Source: ConnectLife has no local API, only its cloud. The open-source `connectlife`
  Python library (used by the connectlife-ha integration) logs in with the app account; the
  collector polls it about once a minute, read-only, with the account in `.env`. It is
  unofficial and can break when ConnectLife changes its API or terms. Decided 2026-10-12: both machines
  are Hisense; the card only shows while a machine runs or is done (then it is gone until the
  next run, after the door has been opened if ConnectLife reports it, otherwise after a tap on
  "Taken out" or two hours). The models are a WF5S1043BW washer (ConnectLife calls it WFSE1114) and a DH3S802BW2 dryer. They
  are not in connectlife-ha's device list, but their siblings are, with the same device type
  codes: the WF5S1045BW washer (type 025) and the DH3S802BW3 dryer (type 030). So support is
  likely; the property mapping may need the two models added. ConnectLife also publishes its own Home Assistant plugin for Hisense
  appliances (Connectlife-LLC/HomeAssistantPlugin), a second reference for the API.
  Built 2026-10-14 (collector and hub). The `connectlife` library is GPL-3.0 and the collector
  image on Docker Hub is public, so the hub has a small client of its own instead (decided
  2026-10-14), written from the MIT-licensed bilan/connectlife-api-connector with the standard
  library: Gigya login, an OAuth token renewed with its refresh token, and the gateway's status call signed with
  ConnectLife's RSA public key (PKCS#1 v1.5, done by hand). The hub logs in with an account of its
  own (CONNECTLIFE_USERNAME/PASSWORD; the owner signs in with Apple) that the machines are shared
  with. Meanings per type from the community mappings: dryer 030 with program names, washer 025
  with statuses and error codes (its program names once it is shared). A machine that stops
  running stays done until its door opens, or two hours. `/api/laundry`; a Laundry card on Home
  after Today (mockup `docs/hub-laundry-mockup.html`). The app's built-in identifiers in the
  client are marked `gitleaks:allow` and listed in `.gitleaksignore`.
  The washer was shared with the hub account on 2026-10-14. Its program numbers do not follow
  the dial, so their names are learnt one wash at a time (9 is Cotton); an unknown one shows as
  "Program 6".
  From 2026-10-16 Gigya refused every login with 403048 ("Api rate limit exceeded") and the card
  stayed hidden on stale data. Fixed 2026-10-19: the login no longer sends the gmid copied from
  the reference (shared by every copy of it), the access token is renewed with the OAuth refresh
  token, and the tokens and the login pause are kept in SQLite (`connectlife_auth`), so a restart
  does not log in again.
  Built 2026-10-21 (Home panel): a Laundry screen while a machine runs or is done: two portholes
  with a ring for the program's progress, water in the door, the minutes left (a check once
  done), the program and "Ready at" or "Take it out", and a headline pill.
- **Calendar** (Now): today's events only. Design (2026-10-10): the next event large with a ring
  counting down to it in its calendar's colour, the day from 07:00 to 23:00 as a ribbon of
  coloured blocks with a glowing now line, then the later events. Read-only, no
  reminders, no bin days. Decided 2026-10-10: CalDAV to `caldav.icloud.com` with an
  app-specific password from the Apple account page, kept in `.env` (it also opens iCloud mail
  and contacts, so NAS-only, revocable any time). All calendars are in Apple Calendar. Settings
  → Desk panels lists them with their colours and a switch each, so some never show; events
  from the chosen ones show with their full titles.
  Built 2026-10-14 (collector and hub): `/api/calendar` every 5 minutes; iCloud's own calendars
  over CalDAV (a REPORT for today), the subscribed ones (GEWIS, Runna, Bartender Shifts, the
  Harry List feeds, the holidays) from their own .ics feeds at most every 15 minutes, without the
  iCloud login; repeating events unfolded with icalendar and recurring-ical-events (decided
  2026-10-14). Subscription addresses stay in memory only, never logged or served; event titles
  never logged. A Today card first on Home and a Calendars section in Settings with a switch per
  calendar (mockup `docs/hub-calendar-mockup.html`).
  Built 2026-10-19 (panel): the Now panel's calendar screen, after the train in the rotation and
  shown on a day with events, as in the panel mockup: the event under way ("Now · Work", minutes
  left) or the next one ("Next · Hubble", minutes to go) large, its ring and light in its
  calendar's colour; the all-day events as chips; the day from 07:00 to 23:00 as a ribbon with
  the now line (past events faded); then the later events, or "Nothing more today". The hub sends
  the events ready to draw (`app/desk_agenda.py`; an event from an earlier day starts at
  midnight; names kept to Latin-1, an emoji is left out), the panel picks now or next on its own
  clock. Building it ran the board out of internal RAM at start-up (ESP-Hosted's packet pools
  live there since the update fix): the screens' data now sits in PSRAM, and the panel logs the
  internal RAM left at start-up (about 100 kB).
- **Headlines** (Now): the top stories from the News reader (M6): the lead story full-bleed over
  its image (proxied by the hub) with the source as a badge, then two more with thumbnails; tap
  one to save it to Readeck, and its bookmark fills.
  Built 2026-10-14 (collector and hub). Decided 2026-10-14: the newest story of each news group,
  the lead the newest with a picture big enough; at the top of News. The feed job keeps each
  article's feed image and a short summary; a `headlines` job every 5 minutes picks the three
  and fetches each picture once (the feed's, else the page's og:image; NU.nl's feed squares are
  asked for at 1280 px, its pages sit behind DPG's consent wall), through the reader's guarded
  client, stored with Pillow as WebP (a 900 px lead and a 240 px square). `/api/news/headlines`
  and `/api/news/headlines/{id}/image/lead|thumb`, which serve only those stored copies (mockup
  `docs/hub-headlines-mockup.html`).
  Built 2026-10-19 (panel; decided 2026-10-19: JPEGs from the hub, saving from the panel comes
  with the device keys): the Now panel's headlines screen, last in the rotation, as in the panel
  mockup: the lead story over its picture with a soft fade, its source as a badge and its age,
  then two more with square thumbnails (a violet tile when a story has none); the bookmarks are
  outlines until the panels can save. `/api/desk/picture/<id>/lead|thumb` serves panel-sized
  baseline JPEGs (640 x 320 and 112 x 112, multiples of 16) made with Pillow from the stored
  WebP copies only; the panel fetches a picture only when a story changes and decodes it with
  the ESP32-P4's JPEG engine into PSRAM.
- **Code** (House): 16 weeks of commit activity as a grid, then the CI state of the default
  branches and running pull requests from the Repos data (M9); a failing build stands out.
  Built 2026-10-14 (collector and hub): the Repos query also reads each default branch's latest
  commit (first line, time, checks) and the five open pull requests updated last with their
  checks, and your GitHub contribution calendar for 16 weeks from a Monday (`github.contributions`
  in config.yaml, the same numbers as the profile, private contributions counted). Decided
  2026-10-14: the builds and pull requests of your and Hubble's repos only, not GEWIS. In the hub
  a Code card at the top of the Repos page (mockup `docs/hub-code-mockup.html`).
  Changed 2026-10-21: on the House panel the Code screen keeps only the commit grid; the builds
  move to the Pipelines card (M21).
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
  Built 2026-10-12 (hub): "Today's movers" on the Portfolio page, from the holdings' weights and
  day moves the collector already serves; on a phone the holdings under 3% share one "N others"
  tile. The indices are the Markets card beside it (mockup `docs/hub-portfolio-mockup.html`).
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
  Built 2026-10-14 (collector and hub): Kuma's status page `sites` (groups Personal and Hubble,
  Kuma's own monitor names) read every minute; the time between heartbeats is added per site to
  its local day as up or down seconds (`site_day`), a day with more than 5 minutes down is an
  outage, less a blip; `/api/sites`. In the hub a My sites section on Services above Outside
  services (mockup `docs/hub-sites-mockup.html`), and the Home status strip counts a site that is
  down. Kuma's status pages are public through status.example.com.
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
  Built 2026-10-12 (collector and hub): `/api/outside-services`, an `outside_services` alert rule, the
  Home tile and the Outside services section on Services (mockup `docs/hub-services-mockup.html`).
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
  Researched 2026-10-14: the living room has an Apple TV 4K (3rd gen) and two HomePods (2nd gen),
  the bedroom an Apple TV 4K (3rd gen, the Wi-Fi-only model, no Thread) and a HomePod mini, the
  bathroom a HomePod mini; the other five are Thread border routers on one network. Every device
  answers unicast DNS-SD at its address (reserved on the router since 2026-10-14), so the
  collector stays on its bridge network. pyatv reads what HomePods play without pairing (the
  living room pair reports its Apple TV); an Apple TV needs AirPlay credentials. Decided
  2026-10-14: pyatv (MIT) in the collector, pinned to 0.18.x as its unicast helper is internal;
  pair the Bedroom Apple TV once; a card on Home (mockup `docs/hub-apple-mockup.html`); the hub
  draws the border routers as one Thread network, not the radio links it cannot see.
  Built 2026-10-14 (collector): `apple` in config.yaml (rooms, names, addresses), read every
  minute; `/api/apple` (per room the devices online or offline since when, their kind, Thread
  state, and what plays) and `/api/apple/artwork/{room}` (fetched once per item, stored as a
  200 px WebP).
  Built 2026-10-14 (hub): an Apple devices card on Home after Laundry: the rooms laid out from
  config.yaml (the first across the top, the others below by their number of devices), each
  device an orb, the room glowing while something plays (ripples from its HomePods, and its
  Apple TV for video), the border routers joined as one Thread network with lines that stop at
  the orbs, an offline device dashed in amber; "N of M online", the Thread count, and a bar per
  room with what plays.
  Built 2026-10-14 (alerts): an `apple_offline` rule warns in the NAS chat when an Apple TV or
  HomePod has not answered for 10 minutes (editable in Alerts → Hub rules, the wording in
  Settings → Messages), and says when it is back; a stale answer never resolves it.
  Built 2026-10-21 (Home panel): an Apple devices screen, the rooms as a plan (the first room
  the left half), each device an orb with its kind (TV, HomePod, mini), amber when offline, the
  room glowing while something plays, "All online" or "N offline", and what plays in a bar below.
  Not yet: the Thread lines and the ripples.
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

**M21. Pipelines** (added 2026-10-21)
- A House screen for the GitHub Actions runs of home_kiosk, community-cafe and harry-list (set in
  config.yaml), read with the hub's existing read-only tokens (Actions: read).
- Decided 2026-10-21: a run on the default branch takes over House, its rotation paused, as a job
  graph like GitHub's run view: one card per job (status icon, name, time, a thin progress line
  from the job's usual length), lines joining the jobs as their `needs` do (home_kiosk: lint,
  test, web, e2e and panels into image), and below it the time so far, "about 3 min left" from
  recent runs, and the commit. Runs on other branches and pull requests do not take over.
- When a run ends, its result stays for 5 minutes, success and failure alike (green "Shipped",
  red "Failed, nothing shipped" with the failing job), then House rotates again. Two runs at once
  take turns every 15 seconds, marked "1 of 2".
- When nothing runs, a quiet card in the House rotation: each repo with its last result and its
  last ten runs on the default branch as bars (height the run time, red for a failure).
- The graph follows each workflow's own jobs, so the other repos' pipelines draw as they are.
  Decided 2026-10-21: the repos are `PimVanLeeuwen/home_kiosk` (collector.yml),
  `Hubble-Community-Cafe/community-cafe-web` (ci.yml) and `Hubble-Community-Cafe/the-harry-list`
  (ci.yml); only that main CI workflow, only when a push to the default branch started it (no
  nightly scans, Security or Dependabot runs). Columns follow `needs` from the workflow file at
  the run's commit (the jobs API has no edges); a matrix job is one card with ×N and a combined
  state, skipped jobs are left out, and names drop their matrix part and wrap to two lines. A run
  waiting at an approval gate (community-cafe-web's "Await publish approval") shows the gate in
  amber for 5 minutes, then House rotates again with the card saying "waiting for approval", and
  the run takes over again once approved. Built 2026-10-21 (collector): `/api/pipelines`
  (`app/sources/pipelines.py`) every 15 s, idle repos once a minute; the "usually" range and the
  idle bars leave out runs over twice the median (a re-run hours later). Built 2026-10-21 (hub):
  House's answer (`app/desk_pipelines.py`): a `pipeline` screen per running or just-finished run
  (cards by stage and row, edges by index, the panel counting the time on from `since`) and the
  `pipelines` idle card; `rotate` follows the rules above. Built 2026-10-21 (panel):
  `screen_pipeline.c` (cards from the hub's columns and rows, the lines painted into a canvas,
  the time counted on from `since`, two pipelines taking turns) and `screen_pipelines.c`, parsed in
  `desk_pipelines.c`. Checked on a real panel: card names lose a trailing part in brackets
  ("E2E (Playwright · full stack)" is "E2E"), and narrow cards (four stages) put the icon on top
  with two lines of name below.
- Decided 2026-10-21: this idle card replaces the build list on the Code screen (M20), which
  keeps its 16-week commit grid; the hub's Code card and Repos page stay as they are.

Order: M1, M2, M3 + M4, M5, M6, M7, M8. M9 slotted in after M2, M10 after M8, then M11. Then
M12, M13, M14, M15, M16, M17, M18, M20 (M19 parked), M21.

## 4. Open items

- Now panel fixes (found 2026-10-20 on the real panel, photo IMG_4833). **Fixed 2026-10-20.**
  - The thin vertical bar at the top right of the calendar screen was LVGL's scrollbar: the
    container for the later events reached past the bottom edge, so the screen could scroll. It
    now takes only the room left, and no panel screen scrolls any more.
  - The freeze after some rotations: the LVGL adapter rotates every frame with the P4's PPA (since
    the picture was turned a quarter for the cases), and ESP-IDF v5.5.6's PPA driver now and then
    never finished such a frame, so the display task waited forever with the display lock held
    (found with a core dump after 104 turns; it also happened once 22 s after a start). Fixed with
    Espressif's own temporary fix in a patched copy of the driver
    (`panels/firmware/components/esp_driver_ppa`); a three-hour run on the bench without a
    freeze. Also: a tap now holds the rotation only when it ends (a press that never ends, such as
    a case pressing on the edge, no longer holds it for good), and every panel logs a `health`
    line every 30 seconds (memory, whether LVGL runs, where the rotation is).
  - Found on the way: the train screen's "On the route" title ran past its box when NS lists
    several stretches; it now wraps.
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
  Radarr, the download clients), watch stats and a per-user leaderboard. **Built 2026-10-14** on
  the Media page (mockup `docs/hub-media-overview-mockup.html`): `/api/media/overview` every five
  minutes from Tracearr's public API v2 (a `trr_pub_` key in .env: each person's plays and watch
  time over 30 days, the household's top genres all time, library counts, this week's additions)
  and Seerr (request counts, the latest requests with title, who asked and where each stands).
  Usernames and display names only; Tracearr's and Seerr's people records also carry emails.
  Jellyseerr was replaced by Seerr on 2026-10-14 (same data, same API and key).
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
