# Desk panels: research notes

Background for plan.md M16 (desk panels), M17 (Hue) and M18 (Spotify), gathered 2026-10-09.
The decisions are in plan.md; this file keeps the facts and links behind them.

## Design

The panels are for information and for home, music and other control, and they must also be
beautiful desk pieces in their own right (decided 2026-10-09). Design quality is part of done.

- **One object.** The three panels share their margins (7.5% of the width), header line, type
  scale and dot position, so they read as one piece on the stand.
- **Light with meaning.** Each panel has an ambient backdrop that says something: Now follows the
  sky through the day; Home glows in the colours the Hue lights in each room have right now, or
  the album's colours while music plays; House stays a quiet violet. An error alert turns all
  three red. The light also falls on the stand, so the stand material matters.
- **Type.** Instrument Sans with tabular figures, as in the hub, rendered as LVGL fonts at a few
  fixed sizes. The screen has 10 px per mm: nothing below 24 px (2.4 mm), body text 30 px and
  up, the clock about 150 px. Labels in spaced capitals, sparingly.
- **IPS, not OLED.** Blacks glow a little, so use deep tinted darks rather than relying on pure
  black, avoid large bright white areas, and lower the backlight at night.
- **Motion.** Calm and smooth: slides and fades of about 400 to 500 ms, no bouncing. At rest only
  the clock, the progress bar and slow ambient changes move.
- **Touch.** Targets at least 9 mm (90 px); hold-and-drag for brightness; swipes between cards.
- **Heavy effects are pre-rendered by the hub** (the blurred album backdrop, gradients) and sent
  as JPEGs, which the P4 decodes in hardware; the panel composes and animates.
- **Physical.** Walnut or oak, or a matte print; no visible cables; the three panels evenly
  spaced and flush.
- **Checked for real.** Every screen is photographed on a real panel on the stand before it
  ships; screenshots and tests alone are not enough.

The mockup ([desk-panels-mockup.html](desk-panels-mockup.html)) shows the direction.

## Board

**Waveshare ESP32-P4-WIFI6-Touch-LCD-4B**, also sold as "ESP32-P4 Smart 86 Box" (Waveshare SKU
31416). Three ordered on Amazon 2026-10-09, not arrived yet.

- ESP32-P4 (dual-core RISC-V), 32 MB PSRAM, 32 MB flash, hardware JPEG decoder.
- 4" IPS, 720 × 720, MIPI DSI (ST7703), GT911 touch (5 points). Outline 86.5 × 86.5 mm, display
  area 71.93 × 71.93 mm. Depth, mounting holes and USB-C position are not published: measure.
- Wi-Fi 6 and Bluetooth 5 through an ESP32-C6 co-processor over SDIO. 2.4 GHz only.
- Power: 5 V over USB-C, or the 5 V and GND pins on the back expansion header.
- ES8311 audio codec with a speaker header (8 Ω, 2 W), two microphones, an RTC battery
  connector. Microphones stay off (plan.md non-goals).
- Not this one: **ESP32-P4-86-Panel-ETH-2RO** (Ethernet, RS485, two relays, 6 to 30 V input).
  Some listings show both; check the model name.

Docs: <https://docs.waveshare.com/ESP32-P4-WIFI6-Touch-LCD-4B> (FAQ under `/FAQ`), examples
<https://github.com/waveshareteam/ESP32-P4-WIFI6-Touch-LCD-4B>, product page
<https://www.waveshare.com/esp32-p4-wifi6-touch-lcd-4b.htm>.

## Firmware

- Plan: ESP-IDF with LVGL 9, one build for all three panels (plan.md M16).
- ESPHome also supports the board: the `mipi_dsi` display has a predefined model
  `WAVESHARE-P4-86-PANEL` (<https://new.esphome.io/components/display/mipi_dsi>), and a community
  LVGL config exists for this exact board:
  <https://github.com/jtenniswood/esphome-lvgl/tree/main/waveshare-esp32-p4-wifi6-touch-lcd-4b>
  (GT911 on GPIO7/8, backlight on GPIO26 with inverted PWM). Useful to check the hardware works
  before the ESP-IDF firmware exists.
- ESP-IDF examples for P4 displays: <https://github.com/embenix/ESP32-P4-DSI-Support-Hub>.

## Where to buy in Europe

- Eckstein (Germany): <https://eckstein-shop.de/esp32-p4-smart-86-box-development-board_1>,
  about EUR 47.59 incl. VAT, item WS31416. Check delivery to the Netherlands.
- Grobotronics (Greece):
  <https://grobotronics.com/waveshare-esp32-p4-smart-86-box-with-touch-display.html?sl=en>
- Amazon.de / Amazon.nl (third-party sellers), Waveshare direct (USD 39.99, ships from China).
- Not found at Tinytronics or Kiwi Electronics in the search; worth checking directly.

## Stand and power

Requirements and options are in plan.md M16. Links:

- A ready-made single-panel desk stand for this board (print three, with supports, not checked
  for fit): <https://makerworld.com/models/2235684>
- A stand for the round 3.4" sibling, for ideas:
  <https://www.printables.com/model/1352883-desk-stand-for-waveshare-esp32-p4-wifi6-touch-lcd>
- Laser cutting in the Netherlands: Snijlab. 3D print services: Craftcloud, JLC3DP. Possibly the
  TU/e maker facilities.

## Hue (M17)

- Local CLIP v2 API on the bridge: HTTPS on the LAN, an application key in the
  `hue-application-key` header, created once by pressing the bridge's link button. No cloud.
- Server-sent events on `/eventstream/clip/v2` push every change (from Apple Home, Siri or a
  switch), grouped per event container.
- Everything in the house is Hue (lights and smart plugs), so Apple Home stays in sync through the
  bridge. Non-Hue HomeKit devices would need Home Assistant.
- Discussion and examples: <https://community.openhab.org/t/philips-hue-clip-2-api-v2-discussion-thread/142111>

## Spotify (M18)

- The owner has Premium. Playback control needs Premium, and since February 2026 so does the
  owner of a development-mode app; new apps get one Client ID and up to 5 users.
  <https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide>
- Redirect URIs must be HTTPS except for loopback (`127.0.0.1`):
  <https://developer.spotify.com/documentation/web-api/concepts/redirect_uri>. The hub's
  Tailscale HTTPS address works, since the browser follows the redirect.
- No push from Spotify: poll the playback state (about every 3 s while playing). Ask for
  `additional_types=episode` to include podcasts.

## Mockup

[desk-panels-mockup.html](desk-panels-mockup.html): the three panels as planned (example
data only). Now: clock and rain, the 07:16 departure (tap Preview for delayed and
cancelled), today's calendar from the chosen calendars, the day view, headlines (tap to save). Home: Now Playing first while music plays (it
stays, as Home never rotates), Bedroom, Hallway and Living room in their light colours (tap, or hold and drag for
brightness), the Desk PC tile (tap to start, tap again for Sleep and Shut down), plugs, scenes lit in
their light colours,
All off. House: NAS as rings, portfolio with a period switch, top movers, code with an activity grid, Jellyfin, backups as
the last 14 nights, alerts (or All quiet). Buttons on the page
start music, switch rotation and night mode, and simulate an error takeover. Album art
and posters are generated colour. Also published
privately as a claude.ai artifact: <https://claude.ai/artifact/7kjiWAz6C8cBu7cArw7j2i>
