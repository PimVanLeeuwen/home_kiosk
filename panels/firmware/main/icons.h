#pragma once

#include "lvgl.h"

/* Small icons drawn as shapes (the panel fonts have none). */
typedef enum { ICON_PLAY, ICON_PAUSE, ICON_NEXT, ICON_PREVIOUS } icon_t;

/* An icon object of `size` pixels in `colour`; change it with icon_set. */
lv_obj_t *icon_create(lv_obj_t *parent, icon_t icon, int size, uint32_t colour);
void icon_set(lv_obj_t *obj, icon_t icon);
