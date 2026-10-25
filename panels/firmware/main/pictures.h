#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Headline pictures for the Now panel (plan.md M20): small JPEGs from the hub,
 * decoded by the ESP32-P4's JPEG engine into PSRAM. */

#define PICTURE_SLOTS 12 /* see desk.h: headlines, cover playing, favourites, last, posters, backgrounds */

typedef struct {
    uint8_t *pixels; /* RGB888 in LVGL's byte order (blue first), in PSRAM; NULL for none */
    int width, height;
} picture_t;

/* Made once, before any picture: the locks (main.c or the first pictures_want). */
void pictures_init(void);

/* The JPEG at `path` on the hub into `into` (from jpeg_alloc_decoder_mem); false when it
 * did not come, or did not fit. */
bool pictures_fetch(const char *path, uint8_t *into, size_t room, size_t *size);

/* Decodes `jpeg` (RGB888, blue first) into `out`, one caller at a time on the one JPEG
 * engine; false when it is not a picture or does not fit in `room`. */
bool pictures_decode_into(const uint8_t *jpeg, size_t size, uint8_t *out, size_t room, int *width, int *height);

/* From the hub task: make sure `slot` shows the picture at `path` ("" for none);
 * fetches and decodes only when it changed. */
void pictures_want(int slot, const char *path);

/* From the LVGL task: a newer picture for `slot`, if there is one. The caller
 * owns it from then on and frees the previous one (heap_caps_free) once it no
 * longer shows it. */
bool pictures_take(int slot, picture_t *picture);
