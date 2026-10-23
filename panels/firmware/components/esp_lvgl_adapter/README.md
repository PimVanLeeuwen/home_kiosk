# esp_lvgl_adapter (patched copy)

`espressif/esp_lvgl_adapter` 0.6.3 (Apache-2.0, Espressif), its `include`, `src`,
build files and licence copied here; `main/idf_component.yml` points the
dependency at this copy with `override_path`.

The one change, in `src/display/bridge/v9/lvgl_bridge_v9.c`,
`copy_unrendered_area_from_front_to_back`: the list of screen pieces left to copy
from the front buffer (`unsync_rects`, `LV_INV_BUF_SIZE * 4 + 4` long) was filled
without a bound. Each dirty area can split every piece it touches into up to four,
so a frame with many small staggered dirty areas (the House panel turning to the
Code screen with its 16 week bars, 2026-10-23) wrote past the array and over the
LVGL task's stack: an `Instruction access fault` and a restart about every minute.
Now the copy stops when the next split would not fit, and the whole screen is
redrawn on the next frame (`lv_async_call`), so at most one frame shows old pixels.

Espressif's latest (0.7.3, and master on 2026-10-23) has the same unbounded array.
Remove this copy once a release bounds it (look for a check on `unsync_cnt` in
that function), and go back to the registry version.
