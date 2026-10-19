#pragma once

#include "lvgl.h"

/* The Now panel's headlines: the lead story over its picture, two more. */
void screen_headlines_create(lv_obj_t *screen);

/* Save story 0 (the lead), 1 or 2, as a tap does (devshot's "save"). Call with
 * the display lock held. */
void screen_headlines_tap(int story);
