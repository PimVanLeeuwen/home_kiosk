# home_kiosk (Home hub)

The household's own website, running on the NAS: one responsive app for the laptop and the
phone, reachable on the LAN and over Tailscale (HTTPS at `https://dev-minotaur.tail1234.ts.net`).
There is no login and nothing is exposed to the internet.

| Section | What it does |
|---------|--------------|
| Home | Status at a glance: NAS health, portfolio, latest news, last backup, services, and the weather (rain in the next 2 hours, from Buienradar) |
| News, Saved | Feeds read in the hub (text only, images through the hub), search, read state; Readeck bookmarks in the same reader |
| Portfolio | Ghostfolio overview: value history, holdings, allocation, holding detail, markets; **Update from DEGIRO** imports new trades |
| NAS, Docker, Backups | Live figures and history, the UPS and its power cuts, what is public on the internet, container load and image updates, rclone runs per volume, storage box space, database dumps, the GitHub mirror |
| Services | Links to every app, LAN or Tailscale depending on how the hub was opened, with live stats |
| Repos | GitHub repos: your own, Hubble and GEWIS, with the backup status of each mirrored repo and when each token expires |
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

## Deploying

A push to `main` runs lint, tests, the web build and e2e, then builds and pushes both images
(`pimvanleeuwen/home-kiosk-collector` and `pimvanleeuwen/home-kiosk-dashboard`, `:latest` and
`:<sha>`). Watchtower on the NAS pulls `:latest` nightly, so anything merged to `main` goes live.
The compose file is copied into `nas-docker/home_kiosk/`; change it here first.

Service icons in `web/src/assets/icons/` come from
[homarr-labs/dashboard-icons](https://github.com/homarr-labs/dashboard-icons) (Apache-2.0, license
in that folder).
