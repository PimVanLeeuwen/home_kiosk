#pragma once

#include "lvgl.h"

/* Arrival motion (plan.md M27, N): when a screen turns in, its ring sweeps, its large
 * number counts up and its charts draw in, once per turn. A screen registers its parts
 * once when it is made; screens.c starts them as it loads the screen, while the light is
 * still down, so the first frame shows them empty. A part that its screen changes while
 * it moves (a new answer) stops where the screen put it. */

/* A ring (lv_arc) or a bar (lv_bar) that sweeps from its start to its value. */
void arrive_sweep(lv_obj_t *obj);

/* A label whose number ("82", "+29.3%", "22,9°") counts up from zero, keeping the
 * label's own words around it. Only for labels without thousands separators. */
void arrive_count(lv_obj_t *label);

/* A chart, placed with lv_obj_set_pos and `width` x `height`, revealed from the left:
 * it is moved into a box of its size that widens. Call once, after placing it. */
void arrive_draw_in(lv_obj_t *obj, int32_t width, int32_t height);

/* Something the screen draws itself (a draw event): redrawn on every step while it moves;
 * its drawing asks `arrive_share` how far along (0 to 1000) to draw. */
void arrive_redraw(lv_obj_t *obj);
int32_t arrive_share(const lv_obj_t *obj);

/* From screens.c: `screen` has just been loaded. */
void arrive_begin(lv_obj_t *screen);
