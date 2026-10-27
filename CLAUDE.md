# home_kiosk (Home hub): notes for Claude

The household's main website and the API behind the three ESP32-P4 desk panels, served from one
stack on the Ugreen NAS. Global rules (git owner-only, no em dashes, ask don't assume, tests required) live in
`~/.claude/CLAUDE.md`; this file adds the project facts. The plan and all decisions are in
[plan.md](plan.md).

## Project rules

- **The kiosk must keep working.** Today the `/kiosk/` carousel; from M16 the three ESP32-P4
  desk panels that replaced the planned Pi kiosk (never built; there is no Pi). Any change to URLs or `/api/*` shapes has to keep them
  rendering.
- **The desk panels are desk pieces.** Information and control, but also beautiful objects:
  design quality is part of done for every panel screen (docs/desk-panels.md, Design).
- **Private, LAN and Tailscale only.** No login, no internet exposure, no third-party CDNs,
  tracking or analytics. Fonts and assets are self-hosted.
- **Never 500 to the frontend.** Every payload carries `as_of` and `stale`; on a source failure
  serve the last good payload with `stale: true`.
- **Secrets are NAS-only** in `.env` (template: `.env.example`). Never in `config.yaml`, code or
  commits.
- **Read-only towards other services**, except the deliberate writes: Readeck (save, archive,
  delete, read progress), Telegram messages, DEGIRO imports into Ghostfolio after you confirm
  them, the living room's Hue lights (switch, dim, white), Spotify playback (play, pause, skip,
  volume, move, start a favourite) and waking the living room Apple TV to open Spotify. Planned
  (M17, M20): the Hue plugs, and saving a headline to Readeck from a panel. Planned (M23):
  Paperless, in its own stack, swaps the label "Paperless" for "Paperless done" on each
  processed mail through the Bridge (its folder stays); the sender inventory only reads. The GitHub mirror only reads from GitHub;
  it writes to `/volume3/backups/github`.
- Style: see plan.md §1. Dark first, violet accent, mono only for technical values.
- **Build pages from `components/ui`:** `Card` or `Surface` for boxes, `states` for loading and
  errors, `Button`, `fieldStyles` and `SearchField`, `Segmented`, `StatTile`, and `PageHeader`'s
  `status` for the page's state. Text sizes come from the type scale (`text-label` …
  `text-giant`) and colours from the theme tokens; a colour outside them is data (brand,
  palette) or neutral shading.

## Architecture

| Path | What it is |
|------|------------|
| `collector/` | Python 3.14 hub API: FastAPI, APScheduler, SQLite (`/app/data`). Image `pimvanleeuwen/home-kiosk-collector` |
| `web/` | Home hub frontend: React, TypeScript, Vite, Tailwind |
| `dashboard/` | Old kiosk carousel (plain HTML/JS), served at `/kiosk/` |
| `caddy/Caddyfile` | One origin on :8083: `web/`, `/kiosk/`, `/api/*` to the collector. Image `pimvanleeuwen/home-kiosk-dashboard` |
| `e2e/` | Playwright, desktop and mobile |
| `docs/kiosk-build-spec.md` | The original kiosk spec: Pi hardware and setup, Ghostfolio pitfalls |
| `docs/desk-panels.md` | Research for the desk panels, Hue and Spotify (M16 to M18); mockup in `docs/desk-panels-mockup.html` |
| `docs/operations.md` | Operating notes: config, deploy, restores, port scan, panel flashing |

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
4. README, docs/operations.md or plan.md updated when behaviour or a decision changes.
5. One-line Conventional Commit message proposed; stop for the owner.

## Decisions log

- 2026-09-30: grow the kiosk into Home hub; keep the Python backend and SQLite; no login; settings
  in SQLite with `config.yaml` as seed; trafilatura for article reading; two Telegram chats
  (NAS alerts, Portfolio). Details in plan.md §1.
- 2026-10-04: GitHub mirror (git history only) of your and Hubble's repos in the collector, an
  exact copy in `/volume3/backups/github` that rclone takes to Hetzner. plan.md M10.
- 2026-10-08: no emoji in Telegram messages; a bold severity word and a monospace table for the
  portfolio report instead. plan.md M11.
- 2026-10-09: no Docker socket proxy; database dumps and restore checks run as a NAS host job,
  so no container gets more Docker access; the PWA is installed from the Tailscale HTTPS
  address. plan.md M12 to M15.
- 2026-10-09: three ESP32-P4 4" touch panels replace the Pi kiosk; Hue control through the
  local bridge API and Spotify playback control become deliberate writes. plan.md M16 to M18.
- 2026-10-10: desk PC power through an ESP32 on the power-button header, on the Home panel;
  panel screens for the train, calendar, headlines, code and Jellyfin; no ambient mode, the
  panels always show their screens. plan.md M19, M20.
- 2026-10-10: the 07:16 train is watched every weekday, Telegram only for problems and past
  quiet hours; the calendar reads iCloud over CalDAV with a per-calendar filter, today only, full
  titles. plan.md M20.
- 2026-10-10: Now Playing moves to the Home panel, which never rotates. plan.md M16, M18.
- 2026-10-10: desk PC power is parked: no ready-made local option. plan.md M19, Open items.
- 2026-10-10: the Home panel controls only the living room (3 White Ambiance spots, 2 white
  bulbs); the Hue plugs are seasonal Christmas switches; no light strips for now. plan.md M17.
- 2026-10-10: status cards on House for the owner's own sites and the outside services in use. plan.md M20.
- 2026-10-10: the scenes card is dropped; Home's second card shows the living room's air, with
  an IKEA ALPSTUGA recommended (Thread through the Apple TVs and HomePods). plan.md M17.
- 2026-10-10: an Apple devices card on Home, as a map of the house (online state, what plays,
  the Thread mesh). plan.md M20.
- 2026-10-12: a laundry card on Home for the Hisense washer and dryer (ConnectLife), read from
  the ConnectLife cloud (no local API), shown only while a machine runs or is done; no
  Telegram for it, the app already notifies. plan.md M20.
- 2026-10-12: outside services are read from their status pages, counting only the components
  the house uses (config.yaml); Hetzner from its page's embedded data, TransIP from TransNOC's
  all-clear sentence; maintenance only while it runs; a Telegram warning when an incident starts
  and ends. plan.md M20.
- 2026-10-13: every desk panel card also gets a view in the hub (the hub mirrors the panels);
  the morning train shows as a card on Home on weekdays from 06:00 until it has left, and is
  watched every weekday with no pause switch; it is also checked the evening before each weekday
  at 20:00 and 22:00, and Home shows it then only when tomorrow's train has a problem. plan.md M20.
- 2026-10-14: Pillow in the collector for headline pictures: each is fetched once and stored as a
  small WebP (900 px lead, 240 px square), so the hub and the panels never load a news site's
  original. plan.md M20.
- 2026-10-14: lights through the Hue Bridge's local API, living room only, on a Lights page (no
  Home card); the hub trusts only Signify's roots and the bridge's own id; live from the bridge's
  event stream. plan.md M17.
- 2026-10-21: the repo is public: history rewritten without household values (old history in
  the private `home_kiosk-archive`), real settings in `collector/config.local.yaml` and the
  `PANEL_HUB_URL` secret; the exposure scan stays in this repo, as its public log only shows a
  count of open ports.
- 2026-10-21: the Home panel rotates while nothing plays; while music plays it stays on Now
  Playing (even with the lights off), and with nothing playing and every light off it shows only
  the light controls (replaces "never rotates", 2026-10-10). plan.md M16.
- 2026-10-22: an ERROR alert takes over all three panels until dismissed on one of them, for all
  three, until it resolves; also in quiet hours; the Alerts screen counts only warnings and
  errors; no Mute 1h for now. plan.md M20.
- 2026-10-23: Watchtower runs the maintained fork `nickfedor/watchtower` (containrrr's was
  archived); same settings and report template.
- 2026-10-23: Paperless-ngx for documents, mail read from Proton Mail through a headless Proton
  Mail Bridge in its stack (never published), senders found with a read-only inventory and
  checked monthly for new ones; no AI on mail or documents. plan.md M23.
- 2026-10-23: AdGuard Home on the NAS only, no extra box: the router hands out the NAS as DNS
  server 1 and Quad9 as server 2, so the internet works when the NAS is down. plan.md M24.
- 2026-10-23: AI with the owner's Anthropic API key for update notes, a morning digest, grouped
  headlines and an alert explainer, capped at EUR 5 a month; no `/ask` in Telegram. plan.md M26.
- 2026-10-25: AI through the official `anthropic` Python SDK; every call goes through
  `app/ai.py`'s `ask()` (feature switch, answer cache by input hash, the monthly cap counted in
  dollars); the Watchtower report waits for the update notes and goes out once. plan.md M26.
- 2026-10-25: each AI feature is off until switched on in Settings, AI. Pinned images: every
  exact version pin with a GitHub source label is checked daily, and Telegram hears only of a
  breaking release. Morning digest: weekdays 06:30, sent through quiet hours, on Home (live,
  after the train) and as the Now panel's Briefing screen until 09:00. Grouped headlines
  replace the headlines on News and the panel; Claude groups and summarises, the hub ranks
  (most feeds, then newest). Alert explainer: container alerts only, as a Telegram reply to the
  alert, with Sonnet's server-side fallback on. plan.md M26.
- 2026-10-25: panels made to look at: screens that are mainly beautiful join the rotation every
  turn (replaces "no ambient mode", 2026-10-10), and every existing screen gets a signature
  visual. The hub paints a screen's rich layer as a 720 x 720 JPEG; the panel adds the live text
  and one or two moving LVGL objects. The photo of the day is picked locally (Immich's people
  first, text-like pictures left out), never by AI. A finished green pipeline leaves House after
  1 minute, a red one after 5. plan.md M27.
- 2026-10-26: runs come from Apple Health through Health Auto Export Premium: the phone posts
  workouts to `/api/runs/health` with `RUNS_KEY` (a write from outside the hub, checked by its key
  instead of same-origin); only runs are kept, on the NAS, and routes never leave it or reach the
  logs. They show on the Now panel. plan.md M28.
- 2026-10-27: the morning briefing is built by the hub in sections (your day, house, markets,
  news, overnight) with Claude writing only the opening, on Sonnet; it takes over the overnight
  digest on the days it goes out; Claude may see tickers and % moves for market notes, never
  amounts or calendar titles beyond the first event. plan.md M29.
- 2026-10-27: an "Explain warnings" button under the morning briefing, shown while alerts are
  open and the Alert explainer is on; a tap has Sonnet explain every open alert (not only
  containers) as a reply to the briefing. plan.md M29.
- 2026-10-27: Tandoor is replaced by a Recipes section in the hub; recipes are JSON in SQLite,
  edited only by pasting JSON (mostly written with Claude), in named prep and cook phases with
  prep first, ingredients flagged pantry or to get; no meal plans, shopping lists, timers or
  in-hub AI. plan.md M30.

## Gotchas

- Ghostfolio: `BASE_CURRENCY` does nothing any more, and exchange rates stay 1:1 until
  Admin → Gather all data has run once. See docs/kiosk-build-spec.md §6.
- node-exporter and Scrutiny listen on the host network: reach them via `host.docker.internal`.
- Readeck listens on 8000 inside the stack but is published on 8084 (8000 is the collector).
- Every endpoint that changes data needs `dependencies=[Depends(same_origin_json)]` (see
  `collector/app/security.py`). Never re-add CORS, and keep `changeOrigin: false` in the Vite
  proxy, or dev writes get a 403.
- Give the owner Tailscale addresses (`https://dev-minotaur.tail870392.ts.net:<port + 10000>` or
  `http://100.93.99.47:<port>`), never the LAN ones (`192.168.1.242`): the LAN addresses do not
  work from the owner's devices.
- On the Mac, the Vite dev proxy can't reach the NAS on its LAN IP (`EHOSTUNREACH`, probably
  macOS Local Network privacy). Point `HUB_API` at the NAS's Tailscale IP on port 8000 (the one
  in `collector/config.local.yaml`).
- APScheduler 3 numbers crontab weekdays from Monday = 0: use day names (`mon-fri`) in cron
  strings, never `1-5`.
- Ghostfolio's per-day `averagePrice` and its first price point are not split-adjusted (NVDA,
  June 2024). The hub despikes the price history and draws today's average instead.
- Playwright runs with service workers blocked (`e2e/playwright.config.ts`) because localhost
  counts as secure and `sw.js` would sit between the specs and their mocked `/api` answers; only
  `e2e/tests/pwa.spec.ts` allows them. A mocked `context.route` keeps answering even with the
  browser offline, so unroute before testing offline behaviour.
- Web tests run in UTC on CI: build expected clock times from local dates
  (`new Date(2026, 9, 6, 10, 2)`), never from `...Z` strings.
- The page area (`<main>` in `Layout.tsx`) has a `view-transition-name`, which makes it a
  stacking context: nothing inside it gets above the tab bar, whatever its z-index. A
  full-screen layer (cook mode) renders into `document.body` with `createPortal`.
- On the phone a `sticky bottom-*` item inside the page area also counts its bottom padding
  (`pb-28`, room for the tab bar): `bottom-0` already sits just above the tab bar.
- Collector tests run in UTC on CI too: run `TZ=UTC pytest` before pushing anything with clock
  times, and read a time without an offset as the configured zone, never the machine's.
- The collector image only builds for linux/amd64 (as CI does): pyatv's miniaudio has no Linux
  arm64 wheel for Python 3.14, so on an Apple silicon Mac use `docker build --platform linux/amd64`.
- The panels' ESP32-P4 is revision v1.3, not the v3.x Waveshare's defaults assume: keep
  `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` and 200 MHz PSRAM; a v3.x build does not boot on them.
  Check every new board with `esptool flash-id` first.
- Flash the panels over the UART USB-C port at 460800 baud; read their flash in 2 MB pieces, as
  one long read breaks off with serial noise.
- On the panels' IPS screens the hub's `#101014` looks grey: panel screens use true black.
- Take panel screenshots with `panels/tools/shot.py`, not photos: opening the port restarts the
  panel on macOS, and the script waits for the hub's answer. Never switch logging off on the panel
  from a task (it locked up core 0).
- `shot.py`'s snapshot renders the screen on the small `devshot` task (8 kB since 2026-10-22,
  when the Services incident card overflowed 4 kB). A panel that restarts on a shot with
  "Stack protection fault" in `devshot`, or ignores every command after one, needs more there;
  the screen itself is fine. After a restart Wi-Fi can take over 20 s, longer than `shot.py` waits.
- LVGL on the panels: hundreds of shapes in one layer stall its task queue (watchdog), and a
  crossfade runs at about 6 fps. Draw busy charts once into a canvas (or paint pixels directly)
  and switch screens with the backlight dip in `screens.c`.
- LVGL's `LV_LABEL_LONG_DOT` only cuts with "…" when the label has a fixed height; with only a
  width it wraps and runs into what is below. For one line use `ui_one_line()`
  (`panels/firmware/main/ui.c`); for more lines set a height or `max_height`.
- The LVGL adapter (`espressif/esp_lvgl_adapter` 0.6.3, and still 0.7.3) overruns its stack when a
  frame has many small staggered dirty areas (`copy_unrendered_area_from_front_to_back`): keep the
  patched copy in `panels/firmware/components/esp_lvgl_adapter` (`override_path`) until a release
  bounds it. A panel that restarts with "Instruction access fault" at a jump to a small address
  on core 0 is the sign.
- A panel reads the hub's answer into one buffer (32 kB since 2026-10-23, 8 kB before) and a cut
  answer cannot be parsed: the board then stays on its start-up screen. Boards send `room=`; the
  hub's `desk.fit` leaves screens out to fit. Keep each screen's payload small (strings and short
  lists, no raw data).
- The panels' ESP32-C6 runs its old factory ESP-Hosted image: keep
  `CONFIG_ESP_HOSTED_MEMPOOL_PREFER_SPIRAM=n` and the streaming SDIO receive, or any larger
  transfer (a firmware update) breaks the Wi-Fi link. A changed `sdkconfig.defaults` does not
  reach an existing `sdkconfig`: move that aside so the build regenerates it.
- Panel firmware: internal RAM is scarce (ESP-Hosted's packet pools live there); keep large
  statics in PSRAM with `EXT_RAM_BSS_ATTR` and never copy a screen's whole state onto a task's
  stack (use the `desk_has_*` checks). Watch "internal RAM free" in the start-up log; a board that
  boot-loops on `vApplicationGetIdleTaskMemory` has run out. Plain `malloc` under 16 kB lands in
  internal RAM: LVGL (`lvgl_memory.c`) and cJSON (hooks in `desk_start()`) allocate from PSRAM for
  that reason. A board stuck on "The hub is not ready ... answered 200", with `H_SDIO_DRV: RX
  buffer alloc failed` right after `clock set from the hub`, has run out there.
- The panels' picture is rotated with the P4's PPA, and ESP-IDF v5.5.6's PPA driver can hang on
  it (display frozen, LVGL waiting in `ppa_do_scale_rotate_mirror`): keep the patched copy in
  `panels/firmware/components/esp_driver_ppa` until the IDF in use has Espressif's fix. After
  adding or removing a project component, run `idf.py reconfigure`, or an existing build keeps
  the old one.
- LVGL on the panels: a `transform_scale` (or rotation) draws the object into a layer every
  frame, and whatever a moving object uncovers is redrawn. Grow shapes by their real size, keep
  them small, and draw big still lights once into a canvas (the takeover went from 6 to 30
  frames a second).
- A new piece on the panels needs a `case` in `screens.c`'s presence switch beside the other
  pieces, or its screen never joins the rotation (it falls through to the board's own screen check).
- A change to a background painter (`app/paint_*.py`) must bump `desk_backgrounds.VERSION`, or
  the hub keeps serving the pictures it already painted.
- Pillow's `Image.radial_gradient` reaches 181 halfway along an edge, not 255: scale by 181
  (`app/paint.py`), or glows end in a square.
- To try a panel change against new hub code before it is deployed: build a copy of
  `panels/firmware` with `CONFIG_PANEL_HUB_URL` pointing at a small pass-through hub on the Mac
  (firmware files come from Caddy on 8083, the API from 8000); afterwards `update.py` puts the
  hub's firmware back.
- CI installs only Chromium's headless shell for e2e, without `--with-deps` (its apt installs
  took about 9 minutes; the runners already have Chrome's libraries). If Chromium ever fails to
  launch on a missing library after a runner image change, add `npx playwright install-deps
  chromium` before the tests.
- GitHub's "Re-run jobs" repeats a run on its original commit; after fixing a workflow, start a
  new run (Run workflow) instead.
- UGREEN's desktop app runs "Sync Space", which is Syncthing (`syncspace_pro`): it opens TCP
  ports on the router through UPnP. UPnP is off on the router since 2026-10-09; the
  `exposure-scan` workflow catches it if something opens a port again.
- Spotify answers 429 with a `Retry-After`; calling again inside that window extends the
  lock-out. The hub pauses every Spotify call until it has passed (`spotify.Client.paused_until`),
  so never add a Spotify call that goes around `Client.call`. The pause is kept in the database
  (`spotify_pause`), so a restart waits too; so is the last answer (`music_last`), so pages and
  panels do not go blank.
- ConnectLife's Gigya login answers 403048 when it rate-limits ("Api rate limit exceeded"),
  and the Laundry card then hides on stale data. Never send a `gmid` copied from a reference
  client (everyone shares it), and keep logins rare: the hub renews with the refresh token and
  keeps tokens and the login pause in SQLite (`connectlife_auth`). The reason is in the
  collector log (Dozzle, :8081), not in `/api/laundry`.
- The collector's real config is `collector/config.local.yaml` (gitignored; on the NAS
  `/volume1/docker/home_kiosk/config.yaml`). `config.yaml` is a public example: never put
  household values (addresses, places, the train, hostnames) in it.
