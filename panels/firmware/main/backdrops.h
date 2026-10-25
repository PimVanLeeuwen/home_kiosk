#pragma once

#include "lvgl.h"

/* Painted backgrounds (plan.md M27): the hub paints a screen's light and texture as a
 * JPEG; the panel keeps it compressed (about 35 kB) and decodes it only for the screen
 * that turns in, into one of two shared buffers, while the light is down. A screen
 * without one stays as it is, on black. (The Clock keeps its own: screen_clock.c.) */

/* From the hub task: the background of screen kind `kind` ("day") is at `path`, or
 * "" for none; fetched only when it changes. */
void backdrops_want(const char *kind, const char *path);

/* When a screen is made: it shows `kind`'s background under everything else. */
void backdrops_attach(lv_obj_t *screen, const char *kind);

/* From screens.c, before it loads `screen`: decodes that screen's background. */
void backdrops_show(lv_obj_t *screen);
