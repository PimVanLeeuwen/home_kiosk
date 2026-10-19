#!/usr/bin/env bash
# Instrument Sans for the panels as LVGL bitmap fonts (plan.md M16): static
# weights cut from Google's variable TTF with fonttools, then converted with
# lv_font_conv. Run from panels/firmware/fonts; writes ../main/fonts/*.c.
# Tools only for this script (a throwaway venv and npx), not project dependencies.
set -euo pipefail
cd "$(dirname "$0")"
SRC="InstrumentSans[wdth,wght].ttf"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 -m venv "$TMP/venv"
"$TMP/venv/bin/pip" install -q fonttools==4.67.0
for weight in 500 600; do
  "$TMP/venv/bin/fonttools" varLib.instancer "$SRC" wght=$weight wdth=100 -q -o "$TMP/is-$weight.ttf"
done

# Latin-1, plus the middle dot and the degree sign it already holds.
TEXT="0x20-0x7E,0xA0-0xFF"
font() {  # name weight size range
  npx -y lv_font_conv@1.5.3 --font "$TMP/is-$2.ttf" -r "$4" --size "$3" --bpp 4 --format lvgl \
    --no-compress --lv-include lvgl.h --lv-font-name "$1" -o "../main/fonts/$1.c"
}
font instrument_clock 500 150 "0x30-0x3A"   # the time: digits and the colon only
font instrument_40 500 40 "$TEXT"           # temperature and weather
font instrument_28_bold 600 28 "$TEXT"      # the rain line
font instrument_24 500 24 "$TEXT"           # the header row
echo "fonts written to ../main/fonts/"
