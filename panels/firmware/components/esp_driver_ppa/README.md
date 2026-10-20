# esp_driver_ppa (patched copy)

ESP-IDF v5.5.6's PPA driver (`components/esp_driver_ppa`, Apache-2.0, Espressif),
copied here so the project's build uses it instead of the IDF's own: ESP-IDF
lets a project override a component by name.

The one change, in `src/ppa_srm.c`: the scale-rotate-mirror transaction always
bypasses the macro-block order. This is Espressif's temporary fix for a PPA hang
(the `0001-bugfix-ppa-Temporary-fix-for-the-PPA-hang-issue.patch` shipped with
`espressif/esp_lvgl_adapter`, written for ESP-IDF v6.0). The desk panels rotate
their picture a quarter turn, which the LVGL adapter does with the PPA; without
the fix the display now and then stopped for good.

Remove this copy once the ESP-IDF version in use contains the fix (check
`ppa_srm.c` for `ppa_ll_srm_bypass_mb_order(platform->hal.dev, true)`), or when
moving to another ESP-IDF version: then copy that version's driver and apply the
change again.
