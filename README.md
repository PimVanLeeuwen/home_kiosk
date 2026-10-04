# home_kiosk (Home hub)

The household's own website, running on the NAS: one responsive app for the laptop and the
phone, reachable on the LAN and over Tailscale (HTTPS at `https://dev-minotaur.tail1234.ts.net`).
There is no login and nothing is exposed to the internet.

| Section | What it does |
|---------|--------------|
| Home | Status at a glance: NAS health, portfolio, latest news, last backup, services |
| News, Saved | Feeds read in the hub (text only, images through the hub), search, read state; Readeck bookmarks in the same reader |
| Portfolio | Ghostfolio overview: value history, holdings, allocation, holding detail, markets; **Update from DEGIRO** imports new trades |
| NAS, Docker, Backups | Live figures and history, container load and image updates, rclone runs per volume, the GitHub mirror |
| Services | Links to every app, LAN or Tailscale depending on how the hub was opened, with live stats |
| Repos | GitHub repos: your own, Hubble and GEWIS, with the backup status of each mirrored repo |
| Alerts | Every Telegram message the hub sends, routing, quiet hours and the hub's own alert rules |
| Settings | Service catalog, news feeds, and the wording of every Telegram message (templates with a live preview and a test send) |

The hub is also the one Telegram sender: backup reports, Watchtower updates, Uptime Kuma, its own
rules, and the weekday portfolio report (08:30 and 18:30). The bot answers `/status`, `/backup`
and `/portfolio` in the two configured chats.

Every night at 02:00 the collector also mirrors all repos of PimVanLeeuwen and
Hubble-Community-Cafe (no forks) as bare git repos into `/volume3/backups/github`, so the 03:00
rclone run takes them to Hetzner. It is an exact copy: a repo deleted on GitHub goes from the mirror
too. Owners are picked with `mirror: true` in `collector/config.yaml`; a failed run goes to Telegram.
To restore one: `git clone /volume3/backups/github/<owner>/<repo>.git`, or push it back to a new
GitHub repo with `git push --mirror <url>` from inside the mirror.

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

## Deploying

A push to `main` runs lint, tests, the web build and e2e, then builds and pushes both images
(`pimvanleeuwen/home-kiosk-collector` and `pimvanleeuwen/home-kiosk-dashboard`, `:latest` and
`:<sha>`). Watchtower on the NAS pulls `:latest` nightly, so anything merged to `main` goes live.
The compose file is copied into `nas-docker/home_kiosk/`; change it here first.

Service icons in `web/src/assets/icons/` come from
[homarr-labs/dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0, license
in that folder).
