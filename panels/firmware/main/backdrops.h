#pragma once

#include <stdbool.h>

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

/* While its screen shows a painted background: `obj` steps aside (the screen's own,
 * plainer light), or turns to glass (a tile the light should show through). */
void backdrops_aside(lv_obj_t *obj);
void backdrops_glass(lv_obj_t *obj);
/* ... or shows only then (it belongs to the painted picture, as the Code city's glow). */
void backdrops_with(lv_obj_t *obj);

/* Whether `screen` shows a painted background now (for a screen that sets its own
 * stepping-aside objects' visibility). */
bool backdrops_painted(const lv_obj_t *screen);

/* From screens.c, before it loads `screen`: decodes that screen's background. */
void backdrops_show(lv_obj_t *screen);
