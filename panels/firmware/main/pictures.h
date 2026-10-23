#pragma once

#include <stdbool.h>
#include <stdint.h>

/* Headline pictures for the Now panel (plan.md M20): small JPEGs from the hub,
 * decoded by the ESP32-P4's JPEG engine into PSRAM. */

#define PICTURE_SLOTS 11 /* see desk.h: headlines, cover playing, favourites, last, posters */

typedef struct {
    uint8_t *pixels; /* RGB888 in LVGL's byte order (blue first), in PSRAM; NULL for none */
    int width, height;
} picture_t;

/* From the hub task: make sure `slot` shows the picture at `path` ("" for none);
 * fetches and decodes only when it changed. */
void pictures_want(int slot, const char *path);

/* From the LVGL task: a newer picture for `slot`, if there is one. The caller
 * owns it from then on and frees the previous one (heap_caps_free) once it no
 * longer shows it. */
bool pictures_take(int slot, picture_t *picture);
