# Operating notes

My notes for running this on my own NAS, desk and accounts: the paths, names and steps are
specific to that setup. The overview is in the [README](../README.md).

## Configuration

- **Secrets** go in `.env` next to the compose file on the NAS; `.env.example` lists every key
  and where to find it. Nothing secret goes in `config.yaml` or the repo.
- **`collector/config.yaml`** is an example of the rest (hosts, places, devices, feeds and
  services to seed, alert chats, portfolio indices and report schedule). Your own copy goes in
  `collector/config.local.yaml`, which git ignores and the collector reads instead when it
  exists. On the NAS it is `/volume1/docker/home_kiosk/config.yaml`, mounted into the
  container by `docker-compose.yml`: put it there before deploying, or the collector runs on the
  example (it logs which file it read). Feeds, services and alert settings are edited in the
  app afterwards; the file only seeds an empty database.
- Senders on the NAS post to `http://<nas>:8000/api/notify` with the `X-Notify-Key` header
  (`NOTIFY_KEY`); see the nas-docker README, *Alerts*.

## Deploying

A push to `main` runs lint, tests, the web build and e2e, then builds and pushes both images
(`pimvanleeuwen/home-kiosk-collector` and `pimvanleeuwen/home-kiosk-dashboard`, `:latest` and
`:<sha>`). Watchtower on the NAS pulls `:latest` nightly, so anything merged to `main` goes live.
The compose file is copied into `nas-docker/home_kiosk/`; change it here first.

## Backups of the hub itself

Every night at 02:00 the collector also mirrors all repos of PimVanLeeuwen and
Hubble-Community-Cafe (no forks) as bare git repos into `/volume3/backups/github`, so the 03:00
rclone run takes them to Hetzner. It is an exact copy: a repo deleted on GitHub goes from the mirror
too. Owners are picked with `mirror: true` in `collector/config.yaml`; a failed run goes to Telegram.
To restore one: `git clone /volume3/backups/github/<owner>/<repo>.git`, or push it back to a new
GitHub repo with `git push --mirror <url>` from inside the mirror.

At 02:45 the collector writes a consistent copy of its own database (`VACUUM INTO`) to
`data/backup/collector.db`, which the 03:00 run takes along. To restore: stop the collector, put
that file in place of `data/collector.db`, and start it again.

## Install on a phone or laptop

The hub is an installable app (a web app manifest and a service worker): it opens full screen
from the home screen, and without the hub it still shows the last data it saw, marked as stale.
Browsers only allow this over HTTPS, so install it from the Tailscale address
(`https://<nas>.<tailnet>.ts.net`), not from `http://<nas LAN IP>:8083`; the LAN address keeps
working as a normal website. On an iPhone: open the Tailscale address in Safari, Share, Add to
Home Screen. A home screen icon made before (a plain bookmark) has to be removed and added again
to become the app. The Pi kiosk at `/kiosk/` is not part of the app.

## Port scan from outside

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

## Desk panels (firmware)

The three ESP32-P4 panels run `panels/firmware` (ESP-IDF v5.5, LVGL 9, Waveshare's board
package). Each board is flashed **once** from the Mac over its **UART** USB-C port with a data
cable, with a build that carries the Wi-Fi details: the board saves them in its own storage.
After that it updates over Wi-Fi: CI builds the firmware (without Wi-Fi details, with the hub
address from the `PANEL_HUB_URL` GitHub secret, for example `http://<the hub's LAN IP>:8083`;
the build fails without it) into the dashboard image, the hub serves it under `/panels/`, and a
board with a different version installs it between 04:00 and 05:00 and restarts. A new firmware that cannot reach the hub
within 5 minutes goes back to the previous one by itself.

```bash
# once: esptool for flashing; the Wi-Fi details in an untracked file
cd panels && python3 -m venv .venv && .venv/bin/pip install esptool==5.6.0
cp firmware/sdkconfig.secrets.example firmware/sdkconfig.secrets   # then fill it in, hub address too

# build (PANEL_VERSION: the version the board reports and compares with the hub's;
# CI uses git's hash of panels/firmware, so a push that leaves it alone changes nothing)
cd panels/firmware && docker run --rm --platform linux/amd64 -e PANEL_VERSION=dev \
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

# install the hub's firmware now instead of at night: "Update now" in Settings, Desk panels
# (within a minute, no cable), or over the cable ("update" on the console)
panels/.venv/bin/python panels/tools/update.py /dev/cu.usbmodem…

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
which keeps its factory ESP-Hosted image (0.0.0): the firmware keeps ESP-Hosted's packet buffers
in internal RAM and uses its streaming receive, as that old image needs.
