/* The House panel's Top movers screen (plan.md M20, the heat map): the holdings as
 * tiles sized by their share of the portfolio and tinted green or red by today's
 * move, stronger for a bigger one (3% is as strong as it gets), as on the hub's
 * Portfolio page; the S&P 500, Nasdaq 100 and AEX below. The hub lays the tiles out
 * and words them (app/desk_movers.py). */

#include "screen_movers.h"

#include <stdlib.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define GAP 3 /* half the space between two tiles */
#define GREEN 0x3fb97f
#define RED 0xe5646a

typedef struct {
    lv_obj_t *box, *ticker, *change, *name;
} tile_t;

static lv_obj_t *title, *total, *indices, *index_labels[DESK_INDICES], *index_changes[DESK_INDICES];
static tile_t tiles[DESK_MOVER_TILES];
EXT_RAM_BSS_ATTR static desk_movers_t shown; /* off the LVGL task's small stack */

/* `colour` at `opa` (0 to 255) over the black screen. */
static lv_color_t over_black(uint32_t colour, int opa)
{
    return lv_color_mix(lv_color_hex(colour), lv_color_black(), (lv_opa_t)opa);
}

static void show_tile(tile_t *t, const typeof(shown.tiles[0]) *tile)
{
    uint32_t colour = tile->move >= 0 ? GREEN : RED;
    int strength = abs(tile->move) > 300 ? 300 : abs(tile->move);
    int opa = 41 + strength * 128 / 300; /* 16% to 66%, as the hub's tint */
    lv_obj_set_pos(t->box, tile->x + GAP, tile->y + GAP);
    lv_obj_set_size(t->box, tile->w - 2 * GAP, tile->h - 2 * GAP);
    lv_obj_set_style_bg_color(t->box, over_black(colour, opa), 0);
    lv_obj_set_style_bg_grad_color(t->box, over_black(colour, opa * 45 / 100), 0);
    lv_obj_set_style_border_color(t->box, over_black(colour, 90), 0);

    bool large = tile->size == 'l', small = tile->size == 's';
    int pad = large ? 16 : 10;
    lv_obj_set_style_text_font(t->ticker, large ? &instrument_28_bold : &instrument_24, 0);
    lv_label_set_text(t->ticker, tile->ticker);
    if (small) {
        /* The smallest tiles only have room for the ticker: centred, edge to edge. */
        lv_obj_set_width(t->ticker, tile->w - 2 * GAP);
        lv_obj_set_style_text_align(t->ticker, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_pos(t->ticker, 0, 8);
    } else {
        lv_obj_set_width(t->ticker, tile->w - 2 * GAP - 2 * pad);
        lv_obj_set_style_text_align(t->ticker, LV_TEXT_ALIGN_LEFT, 0);
        lv_obj_set_pos(t->ticker, pad, large ? 12 : 6);
    }

    lv_obj_set_flag(t->change, LV_OBJ_FLAG_HIDDEN, small);
    lv_label_set_text(t->change, tile->change);
    lv_obj_set_style_text_font(t->change, large ? &instrument_40 : &instrument_24, 0);
    if (large) {
        lv_obj_align(t->change, LV_ALIGN_BOTTOM_LEFT, pad, -44);
    } else {
        lv_obj_set_pos(t->change, pad, 34);
    }

    lv_obj_set_flag(t->name, LV_OBJ_FLAG_HIDDEN, !large || tile->name[0] == '\0');
    lv_label_set_text(t->name, tile->name);
    lv_obj_set_size(t->name, tile->w - 2 * GAP - 2 * pad, 30); /* one line, then "..." */
    lv_obj_align(t->name, LV_ALIGN_BOTTOM_LEFT, pad, -12);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_movers_version() == version) {
        return;
    }
    desk_movers_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(title, shown.title);
    lv_label_set_text(total, shown.total);
    lv_obj_set_style_text_color(total, lv_color_hex(shown.total_up ? 0x5fd39c : 0xff8a8a), 0);
    for (int i = 0; i < DESK_MOVER_TILES; i++) {
        lv_obj_set_flag(tiles[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i < shown.count) {
            show_tile(&tiles[i], &shown.tiles[i]);
        }
    }
    for (int i = 0; i < DESK_INDICES; i++) {
        lv_obj_t *pair = lv_obj_get_parent(index_labels[i]);
        lv_obj_set_flag(pair, LV_OBJ_FLAG_HIDDEN, i >= shown.index_count);
        if (i < shown.index_count) {
            lv_label_set_text(index_labels[i], shown.indices[i].label);
            lv_label_set_text(index_changes[i], shown.indices[i].change);
            lv_obj_set_style_text_color(index_changes[i], lv_color_hex(shown.indices[i].up ? 0x5fd39c : 0xff8a8a), 0);
        }
    }
}

void screen_movers_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    total = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_align(total, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    for (int i = 0; i < DESK_MOVER_TILES; i++) {
        tile_t *t = &tiles[i];
        t->box = ui_plain(screen);
        lv_obj_set_style_radius(t->box, 14, 0);
        lv_obj_set_style_bg_opa(t->box, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_grad_dir(t->box, LV_GRAD_DIR_VER, 0);
        lv_obj_set_style_border_width(t->box, 1, 0);
        lv_obj_add_flag(t->box, LV_OBJ_FLAG_HIDDEN);
        t->ticker = ui_text(t->box, &instrument_24, 0xf1eff7);
        lv_label_set_long_mode(t->ticker, LV_LABEL_LONG_CLIP);
        t->change = ui_text(t->box, &instrument_24, 0xf1eff7);
        t->name = ui_text(t->box, &instrument_24, 0xc9c6d6);
        lv_label_set_long_mode(t->name, LV_LABEL_LONG_DOT);
    }

    /* The indices, spread over the bottom line. */
    indices = ui_plain(screen);
    lv_obj_set_size(indices, 648, LV_SIZE_CONTENT);
    lv_obj_set_pos(indices, LEFT, 660);
    lv_obj_set_layout(indices, LV_LAYOUT_FLEX);
    lv_obj_set_flex_flow(indices, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(indices, LV_FLEX_ALIGN_SPACE_BETWEEN, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    for (int i = 0; i < DESK_INDICES; i++) {
        lv_obj_t *pair = ui_plain(indices);
        lv_obj_set_size(pair, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
        lv_obj_set_layout(pair, LV_LAYOUT_FLEX);
        lv_obj_set_flex_flow(pair, LV_FLEX_FLOW_ROW);
        lv_obj_set_style_pad_column(pair, 10, 0);
        index_labels[i] = ui_text(pair, &instrument_24, 0xa7a7b4);
        index_changes[i] = ui_text(pair, &instrument_24, 0x5fd39c);
    }

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
