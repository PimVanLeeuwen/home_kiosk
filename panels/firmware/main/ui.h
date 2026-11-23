#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "lvgl.h"
#include "pictures.h"

/* The building blocks the panel screens share. */

/* An object without LVGL's default style, neither scrollable nor clickable. */
lv_obj_t *ui_plain(lv_obj_t *parent);

/* An empty label in `font` and `colour`. */
lv_obj_t *ui_text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour);

/* A label of one line, `width` wide, that ends in "..." when the text is
 * longer. LVGL's LV_LABEL_LONG_DOT needs the fixed height: without it the
 * label wraps instead, and runs into whatever is below. */
lv_obj_t *ui_one_line(lv_obj_t *parent, const lv_font_t *font, uint32_t colour, int32_t width);

/* A pill as the hub draws one (M38): its colour as a faint tint behind the words, no edge.
 * Place it with lv_obj_align; `text` gets its label. */
lv_obj_t *ui_pill(lv_obj_t *parent, const lv_font_t *font, lv_obj_t **text);
/* The pill's colour: the words in it, the tint behind them. */
void ui_pill_tone(lv_obj_t *pill, lv_obj_t *text, uint32_t colour);

/* A row of `count` cells (M38): one rounded box cut by 2px hairlines, as the hub's cell
 * grids. Each cell in `cells` is a plain object to place things in with lv_obj_set_pos. */
lv_obj_t *ui_cells(lv_obj_t *parent, int32_t x, int32_t y, int32_t width, int32_t height, int count,
                   lv_obj_t **cells);

/* `from` in capitals (ASCII only), for headers and pills. */
void ui_upper(char *to, size_t size, const char *from);

/* A picture from pictures.c shown on an image object. */
typedef struct {
    lv_obj_t *image;
    picture_t showing; /* NULL pixels: none */
    lv_image_dsc_t dsc;
} ui_picture_t;

/* From the LVGL task: shows the newer picture for `slot`, if there is one
 * (hiding the image when it is none), and frees the one it replaces. */
void ui_take_picture(int slot, ui_picture_t *picture);
