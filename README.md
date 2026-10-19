# home_kiosk (Home hub)

The household's own website, running on the NAS: one responsive app for the laptop and the
phone, reachable on the LAN and over Tailscale (HTTPS at `https://dev-minotaur.tail1234.ts.net`).
There is no login and nothing is exposed to the internet.

| Section | What it does |
|---------|--------------|
| Home | Status at a glance: the washer and dryer while one runs or is done (ConnectLife), today's calendar (iCloud and subscribed calendars, the next event with a countdown and the day as a ribbon), NAS health, portfolio, latest news, last backup, services, the weather (rain in the next 2 hours, from Buienradar), and the outside services the house depends on; on weekday mornings the 07:16 to Rotterdam Centraal until it leaves (NS: delay, platform, cancellation with the next direct train, works on the route), and the evening before when tomorrow's train has a problem, with Telegram warnings for both |
| News, Saved | Feeds read in the hub (text only, images through the hub), search, read state; Readeck bookmarks in the same reader |
| Portfolio | Ghostfolio overview: value history, holdings, allocation, holding detail, markets; **Update from DEGIRO** imports new trades |
| NAS, Docker, Backups | Live figures and history, the UPS and its power cuts, what is public on the internet, container load and image updates, rclone runs per volume, storage box space, database dumps, the GitHub mirror |
| Media | What needs attention in the media stack, from Sonarr and Radarr: downloads with poster, progress and time left (stalled or failed ones with their reason), aired episodes that are missing, and what airs in the coming week; Seerr's requests and where they stand, who watched how much in 30 days (Tracearr) and the library's size |
| Services | Links to every app, LAN or Tailscale depending on how the hub was opened, with live stats; my own websites as 30-day uptime rings from Uptime Kuma; the status of GitHub, Cloudflare, Docker Hub, Tailscale, Hetzner, TransIP and Proton with any open incident |
| Tailscale | The tailnet as a map around the NAS and every device on it: MagicDNS name, addresses, direct, relay or idle, exit node, last seen, and tailscaled's own health warnings (read-only, from the NAS's tailscaled) |
| Repos | GitHub repos: your own, Hubble and GEWIS, with the backup status of each mirrored repo and when each token expires |
| Alerts | Every Telegram message the hub sends, routing, quiet hours and the hub's own alert rules |
| Settings | Service catalog, news feeds, which calendars show, and the wording of every Telegram message (templates with a live preview and a test send) |

The hub is also the one Telegram sender: backup reports, Watchtower updates, Uptime Kuma, its own
rules, and the weekday portfolio report (08:30 and 18:30). The bot answers `/status`, `/backup`
and `/portfolio` in the two configured chats.

Every night at 02:00 the collector also mirrors all repos of PimVanLeeuwen and
Hubble-Community-Cafe (no forks) as bare git repos into `/volume3/backups/github`, so the 03:00
rclone run takes them to Hetzner. It is an exact copy: a repo deleted on GitHub goes from the mirror
too. Owners are picked with `mirror: true` in `collector/config.yaml`; a failed run goes to Telegram.
To restore one: `git clone /volume3/backups/github/<owner>/<repo>.git`, or push it back to a new
GitHub repo with `git push --mirror <url>` from inside the mirror.

At 02:45 the collector writes a consistent copy of its own database (`VACUUM INTO`) to
`data/backup/collector.db`, which the 03:00 run takes along. To restore: stop the collector, put
that file in place of `data/collector.db`, and start it again.

The old 720×1280 desk carousel still lives at `/kiosk/` (add `?data=api` for live data).

## How it fits together

| Path | What it is |
|------|------------|
| `collector/` | Python API (FastAPI, APScheduler, SQLite in `/app/data`): collects, caches and serves everything under `/api` |
| `web/` | The hub (React, TypeScript, Vite, Tailwind) |
| `dashboard/` | The old kiosk carousel, served at `/kiosk/` |
| `caddy/Caddyfile` | One origin on :8083: the hub, `/kiosk/`, and `/api/*` to the collector |
| `e2e/` | Playwright tests against the built image, desktop and mobile |

Every collector job caches its last good result; when a source fails the hub keeps showing it,
marked as out of date. Writes (settings, Readeck, alerts, the DEGIRO import) only accept
same-origin JSON requests.

## Configuration

- **Secrets** go in `.env` next to the compose file on the NAS; `.env.example` lists every key
  and where to find it. Nothing secret goes in `config.yaml` or the repo.
- **`collector/config.yaml`** holds the rest (hosts, feeds and services to seed, alert chats,
  portfolio indices and report schedule). Feeds, services and alert settings are edited in the
  app afterwards; the file only seeds an empty database.
- Senders on the NAS post to `http://<nas>:8000/api/notify` with the `X-Notify-Key` header
  (`NOTIFY_KEY`); see the nas-docker README, *Alerts*.

### Install on a phone or laptop

The hub is an installable app (a web app manifest and a service worker): it opens full screen
from the home screen, and without the hub it still shows the last data it saw, marked as stale.
Browsers only allow this over HTTPS, so install it from the Tailscale address
(`https://<nas>.<tailnet>.ts.net`), not from `http://192.168.1.10:8083`; the LAN address keeps
working as a normal website. On an iPhone: open the Tailscale address in Safari, Share, Add to
Home Screen. A home screen icon made before (a plain bookmark) has to be removed and added again
to become the app. The Pi kiosk at `/kiosk/` is not part of the app.

### Port scan from outside

The house needs no open port (Tandoor and CouchDB go through the Cloudflare tunnel), and the NAS
page's Exposure card shows the proof: `.github/workflows/exposure-scan.yml` runs nightly on
GitHub, joins the tailnet as a temporary node, asks the hub for the current home IP, scans every
TCP port over the normal internet and posts the result back. The hub alerts on any open port, and
when no good scan came in for 48 hours. One-time setup:

1. **Tailscale policy** (admin console, Access controls): add the tag and let it reach only the
   hub's API, not the rest of the tailnet. If the policy still has the default allow-all rule,
   narrow that first, or the tagged node can reach everything.
   ```json
   "tagOwners": { "tag:exposure-scan": ["autogroup:admin"] },
   "grants": [ { "src": ["tag:exposure-scan"], "dst": ["<the NAS's tailnet IP>"], "ip": ["tcp:8000"] } ]
   ```
2. **Tailscale OAuth client** (Settings, OAuth clients): scope *Auth Keys: write*, tag
   `tag:exposure-scan`.
3. **GitHub secrets** (this repo, Settings, Secrets and variables, Actions): `TS_OAUTH_CLIENT_ID`,
   `TS_OAUTH_SECRET`, `HUB_URL` (`http://<the NAS's tailnet IP>:8000`) and `NOTIFY_KEY` (the
   hub's).
4. Run it once by hand (Actions, exposure-scan, Run workflow) and check the Exposure card.

## Developing

```bash
# collector
cd collector && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
ruff check . && pytest
uvicorn app.main:app --reload --port 8000

# web (proxies /api to HUB_API, default http://localhost:8000)
cd web && npm install && npm run test:run && npm run lint && npm run build
npm run dev

# end to end: builds and runs the dashboard image, so Docker must be running
cd e2e && npm ci && npx playwright test
```

## Desk panels (firmware)

The three ESP32-P4 panels run `panels/firmware` (ESP-IDF v5.5, LVGL 9, Waveshare's board
package). It is built in Espressif's Docker image and flashed from the Mac with esptool, over the
board's **UART** USB-C port with a data cable.

```bash
# once: esptool for flashing; the Wi-Fi details in an untracked file
cd panels && python3 -m venv .venv && .venv/bin/pip install esptool==5.6.0
cp firmware/sdkconfig.secrets.example firmware/sdkconfig.secrets   # then fill it in

# build
# (PANEL_VERSION: the firmware version the board reports to the hub, the commit)
cd panels/firmware && docker run --rm --platform linux/amd64 -e PANEL_VERSION=$(git rev-parse --short HEAD) \
  -v "$PWD":/project -w /project espressif/idf:v5.5.6 idf.py build

# before the first flash of a board: its chip revision, and a backup of the factory flash
# (2 MB at a time: long reads over this link break off)
.venv/bin/esptool --port /dev/cu.usbmodem… flash-id
.venv/bin/esptool --port /dev/cu.usbmodem… --baud 921600 read-flash <offset> 0x200000 part.bin

# flash
cd panels/firmware/build && ../../.venv/bin/esptool --chip esp32p4 --port /dev/cu.usbmodem… \
  --baud 460800 --before default-reset --after hard-reset write-flash @flash_args


# a screenshot of what a panel shows, as a PNG (opening the port restarts the panel;
# the script waits until it has the hub's answer); a last argument of 1, 2, ... turns to a
# later screen first ("next" on the console), and the screen is held while it is captured
panels/.venv/bin/pip install pillow==12.3.0   # once
panels/.venv/bin/python panels/tools/shot.py /dev/cu.usbmodem… screen.png [1]

# the panel fonts: Instrument Sans as LVGL bitmap fonts (writes firmware/main/fonts/*.c)
cd panels/firmware/fonts && ./make-fonts.sh
```

The panel's console (logs, screenshots) runs at **921600 baud**; only the boot ROM's first lines
are at 115200. The glows are alpha-only images from `firmware/images/make-glows.py`.

Every board runs the same build and asks the hub by its MAC address (the one esptool prints,
written on its back). A new board shows "Which panel is this?" with its MAC; choose its panel in
the hub under Settings, Desk panels.

The boards have an ESP32-P4 **v1.3**: the firmware is built for revisions below 3.0, and a build
for v3.x chips does not boot on them (nor the other way round). Wi-Fi goes through the ESP32-C6,
which keeps its factory ESP-Hosted image.

## Deploying

A push to `main` runs lint, tests, the web build and e2e, then builds and pushes both images
(`pimvanleeuwen/home-kiosk-collector` and `pimvanleeuwen/home-kiosk-dashboard`, `:latest` and
`:<sha>`). Watchtower on the NAS pulls `:latest` nightly, so anything merged to `main` goes live.
The compose file is copied into `nas-docker/home_kiosk/`; change it here first.

Service icons in `web/src/assets/icons/` come from
[homarr-labs/dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0, license
in that folder).
