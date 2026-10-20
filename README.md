# home_kiosk (Home hub)

My household's own dashboard: a website for the laptop and the phone, and three small touch
panels on my desk, all served by my NAS. It shows the state of the house and the things I keep an
eye on (the NAS and its backups, my portfolio, the news, the media stack, my train, the lights and
the music) and sends the household's Telegram alerts. It is reachable on the LAN and over
Tailscale only, with no login and nothing exposed to the internet.

> **A personal project.** This is built for one household: my NAS, my devices, my accounts and my
> routines. It is not a product, it makes no attempt to be configurable for anyone else, and there
> is no guide to running it elsewhere. The code is here to read and to borrow from under the
> [MIT license](LICENSE); issues and pull requests are not expected.

## What it does

| Section | What it does |
|---------|--------------|
| Home | Status at a glance: the washer and dryer while one runs or is done (ConnectLife), today's calendar (iCloud and subscribed calendars, the next event with a countdown and the day as a ribbon), NAS health, portfolio, latest news, last backup, services, the weather (rain in the next 2 hours, from Buienradar), and the outside services the house depends on; on weekday mornings my train to work until it leaves (NS: delay, platform, cancellation with the next direct train, works on the route), and the evening before when tomorrow's train has a problem, with Telegram warnings for both |
| News, Saved | Feeds read in the hub (text only, images through the hub), search, read state; Readeck bookmarks in the same reader |
| Portfolio | Ghostfolio overview: value history, holdings, allocation, holding detail, markets; **Update from DEGIRO** imports new trades |
| NAS, Docker, Backups | Live figures and history, the UPS and its power cuts, what is public on the internet, container load and image updates, rclone runs per volume, storage box space, database dumps, the GitHub mirror |
| Media | What needs attention in the media stack, from Sonarr and Radarr: downloads with poster, progress and time left (stalled or failed ones with their reason), aired episodes that are missing, and what airs in the coming week; Seerr's requests and where they stand, who watched how much in 30 days (Tracearr) and the library's size |
| Services | Links to every app, LAN or Tailscale depending on how the hub was opened, with live stats; my websites as 30-day uptime rings from Uptime Kuma; the status of GitHub, Cloudflare, Docker Hub, Tailscale, Hetzner, TransIP and Proton with any open incident |
| Lights | The living room's Hue lights through the bridge's local API: on, off, dim and white, live from the bridge |
| Music | Spotify: what plays, the controls, my devices and favourites, and waking the living room Apple TV to play there |
| Tailscale | The tailnet as a map around the NAS and every device on it: MagicDNS name, addresses, direct, relay or idle, exit node, last seen, and tailscaled's own health warnings (read-only, from the NAS's tailscaled) |
| Repos | GitHub repos: mine, Hubble and GEWIS, with the backup status of each mirrored repo and when each token expires |
| Alerts | Every Telegram message the hub sends, routing, quiet hours and the hub's own alert rules |
| Settings | One page per section (`/settings/<section>`): service catalog, news feeds, which calendars show, Spotify and its favourites, which board is which desk panel, and the wording of every Telegram message (folded by group; templates with a live preview and a test send) |

The hub is also the household's one Telegram sender (backup reports, container updates, uptime,
its own alert rules and a weekday portfolio report), and the bot answers a few commands. Every
night it mirrors my GitHub repos into the NAS backups and makes a copy of its own database.

The **desk panels** are three 4" ESP32-P4 touch screens (Now, Home and House) that show the
hub's cards: the time and weather, my train, the calendar, headlines, now playing, the living
room's lights, the NAS and the portfolio. The old 720×1280 desk carousel still lives at `/kiosk/`.

## How it fits together

| Path | What it is |
|------|------------|
| `collector/` | Python API (FastAPI, APScheduler, SQLite in `/app/data`): collects, caches and serves everything under `/api` |
| `web/` | The hub (React, TypeScript, Vite, Tailwind) |
| `dashboard/` | The old kiosk carousel, served at `/kiosk/` |
| `caddy/Caddyfile` | One origin on :8083: the hub, `/kiosk/`, and `/api/*` to the collector |
| `panels/` | Firmware for the three ESP32-P4 desk panels, and tools to flash and screenshot them |
| `e2e/` | Playwright tests against the built image, desktop and mobile |
| `docs/` | Design mockups, the original kiosk spec, the desk panel research, and my [operating notes](docs/operations.md) |

Every collector job caches its last good result; when a source fails the hub keeps showing it,
marked as out of date. Writes (settings, Readeck, alerts, lights, music, the DEGIRO import) only
accept same-origin JSON requests. The household's own settings (hosts, places, devices) live in a
config file outside the repo; `collector/config.yaml` is an example. Pushes to `main` build the
images that the NAS picks up nightly.

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

My notes on configuring, deploying and running it (the NAS, the panels, the port scan) are in
[docs/operations.md](docs/operations.md).

## License

MIT, see [LICENSE](LICENSE), except for these third-party files:

- Service icons in `web/src/assets/icons/` come from
  [homarr-labs/dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0, license
  in that folder).
- The fonts (Instrument Sans, JetBrains Mono) in `web/src/assets/fonts/`,
  `dashboard/assets/fonts/` and `panels/firmware/fonts/` are under the SIL Open Font License 1.1
  (`OFL.txt` beside them).
