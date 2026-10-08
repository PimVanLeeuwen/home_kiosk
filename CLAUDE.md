# home_kiosk (Home hub): notes for Claude

The household's main website and the 720×1280 Pi desk kiosk, served from one stack on the Ugreen
NAS. Global rules (git owner-only, no em dashes, ask don't assume, tests required) live in
`~/.claude/CLAUDE.md`; this file adds the project facts. The plan and all decisions are in
[plan.md](plan.md).

## Project rules

- **The Pi kiosk must keep working.** It is a dumb Chromium on a Pi pointed at this stack; any
  change to URLs or `/api/*` shapes has to keep it rendering.
- **Private, LAN and Tailscale only.** No login, no internet exposure, no third-party CDNs,
  tracking or analytics. Fonts and assets are self-hosted.
- **Never 500 to the frontend.** Every payload carries `as_of` and `stale`; on a source failure
  serve the last good payload with `stale: true`.
- **Secrets are NAS-only** in `.env` (template: `.env.example`). Never in `config.yaml`, code or
  commits.
- **Read-only towards other services**, except the deliberate writes: Readeck (save, archive,
  delete, read progress), Telegram messages, and DEGIRO imports into Ghostfolio after you confirm
  them. The GitHub mirror only reads from GitHub; it writes to `/volume3/backups/github`.
- Style: see plan.md §1. Dark first, violet accent, mono only for technical values.

## Architecture

| Path | What it is |
|------|------------|
| `collector/` | Python 3.14 hub API: FastAPI, APScheduler, SQLite (`/app/data`). Image `pimvanleeuwen/home-kiosk-collector` |
| `web/` | Home hub frontend: React, TypeScript, Vite, Tailwind |
| `dashboard/` | Old kiosk carousel (plain HTML/JS), served at `/kiosk/` |
| `caddy/Caddyfile` | One origin on :8083: `web/`, `/kiosk/`, `/api/*` to the collector. Image `pimvanleeuwen/home-kiosk-dashboard` |
| `e2e/` | Playwright, desktop and mobile |
| `docs/kiosk-build-spec.md` | The original kiosk spec: Pi hardware and setup, Ghostfolio pitfalls |

## Commands

```bash
# collector
cd collector && python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
ruff check . && pytest
uvicorn app.main:app --reload --port 8000

# web
cd web && npm install && npm run test:run && npm run build && npm run lint
npm run dev

# e2e: builds and runs the dashboard image, so Docker must be running
cd e2e && npm ci && npx playwright test

# old kiosk against fixtures
python3 dashboard/serve.py
```

## Deployment

- A push to `main` builds and pushes both images (`:latest` and `:<sha>`); Watchtower on the NAS
  pulls `:latest` nightly. **Anything merged to `main` goes live**, so unfinished work stays on a
  branch.
- The compose file is copied into `nas-docker/home_kiosk/`; change it here first.

## Definition of done (per step)

1. Tests added or updated (pytest beside the collector, Vitest beside the component). Pages cover
   loading, empty, error and stale states.
2. `ruff`, `pytest`, web tests, build and lint green; Playwright spec updated for user-facing
   changes (desktop and mobile).
3. Visual change: desktop and mobile screenshots saved to
   `~/Pictures/pr-screenshots/home_kiosk/<branch>/` and shown in chat.
4. README / plan.md updated when behaviour or a decision changes.
5. One-line Conventional Commit message proposed; stop for the owner.

## Decisions log

- 2026-09-30: grow the kiosk into Home hub; keep the Python backend and SQLite; no login; settings
  in SQLite with `config.yaml` as seed; trafilatura for article reading; two Telegram chats
  (NAS alerts, Portfolio). Details in plan.md §1.
- 2026-10-04: GitHub mirror (git history only) of your and Hubble's repos in the collector, an
  exact copy in `/volume3/backups/github` that rclone takes to Hetzner. plan.md M10.
- 2026-10-08: no emoji in Telegram messages; a bold severity word and a monospace table for the
  portfolio report instead. plan.md M11.

## Gotchas

- Ghostfolio: `BASE_CURRENCY` does nothing any more, and exchange rates stay 1:1 until
  Admin → Gather all data has run once. See docs/kiosk-build-spec.md §6.
- node-exporter and Scrutiny listen on the host network: reach them via `host.docker.internal`.
- Readeck listens on 8000 inside the stack but is published on 8084 (8000 is the collector).
- Every endpoint that changes data needs `dependencies=[Depends(same_origin_json)]` (see
  `collector/app/security.py`). Never re-add CORS, and keep `changeOrigin: false` in the Vite
  proxy, or dev writes get a 403.
- On the Mac, the Vite dev proxy can't reach the NAS on its LAN IP (`EHOSTUNREACH`, probably
  macOS Local Network privacy). Point `HUB_API` at the Tailscale IP `http://100.70.0.10:8000`.
- APScheduler 3 numbers crontab weekdays from Monday = 0: use day names (`mon-fri`) in cron
  strings, never `1-5`.
- Ghostfolio's per-day `averagePrice` and its first price point are not split-adjusted (NVDA,
  June 2024). The hub despikes the price history and draws today's average instead.
