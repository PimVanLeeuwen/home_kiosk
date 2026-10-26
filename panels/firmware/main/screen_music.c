/* The Home panel's music (plan.md M18; the cover wall, M27 M): eight covers over the colour
 * of what plays, the hub's painted wash (app/paint_music.py, the same grid). The favourites
 * on top, the playlists and albums played lately below, each a tap to play: a favourite on
 * the device that plays, else the living room's Apple TV, woken when needed; the one that
 * plays has a light rim and a small equaliser. A line at the foot says what plays. */

#include "screen_music.h"

#include <stdio.h>
#include <string.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "pictures.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define WIDTH 648
#define COVER 144 /* the hub's "wall" covers */
#define GAP 24
#define PER_ROW 4
static const int ROW_TOP[2] = {136, 392}; /* the covers' tops, as app/paint_music.py has them */

typedef struct {
    lv_obj_t *tile, *art, *name, *eq;
    ui_picture_t cover;
} tile_t;

static lv_obj_t *label_device, *headings[2], *footer;
static tile_t tiles[2][PER_ROW]; /* [0] the favourites, [1] played lately */
EXT_RAM_BSS_ATTR static desk_music_t shown; /* off the LVGL task's small stack */

static void on_tile(lv_event_t *event)
{
    int at = (int)(intptr_t)lv_event_get_user_data(event);
    int row = at / PER_ROW, i = at % PER_ROW;
    char what[24];
    if (row == 0 && i < shown.count) {
        snprintf(what, sizeof what, "favourite/%d", shown.favourites[i].position);
    } else if (row == 1 && i < shown.recent_count) {
        snprintf(what, sizeof what, "recent/%d", i);
    } else {
        return;
    }
    if (actions_music(what)) {
        /* The rim lights at once: it may take the Apple TV a few seconds to wake. */
        lv_obj_set_style_border_opa(tiles[row][i].art, LV_OPA_COVER, 0);
    }
}

static void show_tile(tile_t *t, bool here, const char *name, uint32_t colour, bool playing)
{
    lv_obj_set_flag(t->tile, LV_OBJ_FLAG_HIDDEN, !here);
    if (!here) {
        return;
    }
    lv_label_set_text(t->name, name);
    lv_obj_set_style_bg_color(t->art, lv_color_hex(colour), 0); /* until the cover is in */
    lv_obj_set_style_border_opa(t->art, playing ? 220 : 0, 0);
    lv_obj_set_style_shadow_opa(t->art, playing ? 120 : 0, 0);
    lv_obj_set_style_shadow_color(t->art, lv_color_hex(colour), 0);
    lv_obj_set_flag(t->eq, LV_OBJ_FLAG_HIDDEN, !playing);
}

static void tick(lv_timer_t *timer)
{
    for (int i = 0; i < PER_ROW; i++) {
        ui_take_picture(PICTURE_FAVOURITE + i, &tiles[0][i].cover);
        ui_take_picture(PICTURE_RECENT + i, &tiles[1][i].cover);
    }
    static uint32_t version;
    if (desk_music_version() == version) {
        return;
    }
    shown = desk_music();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    char caps[64];
    ui_upper(caps, sizeof caps, shown.device);
    lv_label_set_text(label_device, caps);
    lv_obj_set_flag(lv_obj_get_parent(label_device), LV_OBJ_FLAG_HIDDEN, shown.device[0] == '\0');
    lv_obj_set_flag(headings[0], LV_OBJ_FLAG_HIDDEN, shown.count == 0);
    lv_obj_set_flag(headings[1], LV_OBJ_FLAG_HIDDEN, shown.recent_count == 0);
    for (int i = 0; i < PER_ROW; i++) {
        show_tile(&tiles[0][i], i < shown.count, shown.favourites[i].name, shown.favourites[i].colour,
                  shown.favourites[i].playing);
        show_tile(&tiles[1][i], i < shown.recent_count, shown.recent[i].name, shown.recent[i].colour,
                  shown.recent[i].playing);
    }
    lv_label_set_text(footer, shown.footer);
}

/* Three still bars on a dark chip in the corner of the cover that plays, so they read on
 * any cover. */
static lv_obj_t *eq_create(lv_obj_t *parent)
{
    lv_obj_t *eq = ui_plain(parent);
    lv_obj_set_size(eq, 44, 40);
    lv_obj_align(eq, LV_ALIGN_BOTTOM_RIGHT, -8, -8);
    lv_obj_set_style_radius(eq, 10, 0);
    lv_obj_set_style_bg_opa(eq, 170, 0);
    lv_obj_set_style_bg_color(eq, lv_color_hex(0x0b0a10), 0);
    static const int HEIGHTS[3] = {14, 24, 18};
    for (int b = 0; b < 3; b++) {
        lv_obj_t *bar = ui_plain(eq);
        lv_obj_set_size(bar, 6, HEIGHTS[b]);
        lv_obj_set_pos(bar, 9 + b * 10, 32 - HEIGHTS[b]);
        lv_obj_set_style_radius(bar, 3, 0);
        lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(bar, lv_color_white(), 0);
    }
    lv_obj_add_flag(eq, LV_OBJ_FLAG_HIDDEN);
    return eq;
}

void screen_music_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *header = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "MUSIC");
    lv_obj_set_pos(header, LEFT, 30);
    lv_obj_t *pill = ui_plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 6, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_opa(pill, 40, 0);
    lv_obj_set_style_bg_color(pill, lv_color_white(), 0);
    lv_obj_set_style_border_width(pill, 2, 0);
    lv_obj_set_style_border_color(pill, lv_color_white(), 0);
    lv_obj_set_style_border_opa(pill, 50, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 22);
    label_device = ui_text(pill, &instrument_24, 0xe6e3ef);
    lv_obj_set_style_text_letter_space(label_device, 1, 0);

    static const char *const HEADINGS[2] = {"FAVOURITES", "PLAYED LATELY"};
    for (int row = 0; row < 2; row++) {
        headings[row] = ui_text(screen, &instrument_24, 0x8a8794);
        lv_obj_set_style_text_letter_space(headings[row], 2, 0);
        lv_label_set_text(headings[row], HEADINGS[row]);
        lv_obj_set_pos(headings[row], LEFT, ROW_TOP[row] - 40);
        lv_obj_add_flag(headings[row], LV_OBJ_FLAG_HIDDEN);

        for (int i = 0; i < PER_ROW; i++) {
            tile_t *t = &tiles[row][i];
            t->tile = ui_plain(screen);
            lv_obj_set_size(t->tile, COVER, COVER + 44);
            lv_obj_set_pos(t->tile, LEFT + i * (COVER + GAP), ROW_TOP[row]);
            lv_obj_add_flag(t->tile, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_add_event_cb(t->tile, on_tile, LV_EVENT_CLICKED, (void *)(intptr_t)(row * PER_ROW + i));

            t->art = ui_plain(t->tile);
            lv_obj_set_size(t->art, COVER, COVER);
            lv_obj_set_style_radius(t->art, 16, 0);
            lv_obj_set_style_clip_corner(t->art, true, 0);
            lv_obj_set_style_bg_opa(t->art, LV_OPA_COVER, 0);
            lv_obj_set_style_bg_color(t->art, lv_color_hex(0x1a1920), 0);
            lv_obj_set_style_border_width(t->art, 4, 0);
            lv_obj_set_style_border_color(t->art, lv_color_hex(0xe2dcff), 0);
            lv_obj_set_style_border_opa(t->art, 0, 0);
            lv_obj_set_style_border_post(t->art, true, 0); /* the rim over the cover */
            lv_obj_set_style_shadow_width(t->art, 40, 0);
            lv_obj_set_style_shadow_opa(t->art, 0, 0);
            t->cover.image = lv_image_create(t->art);
            lv_obj_center(t->cover.image);
            lv_obj_add_flag(t->cover.image, LV_OBJ_FLAG_HIDDEN);
            t->eq = eq_create(t->art);

            t->name = ui_one_line(t->tile, &instrument_24, 0xf1eff7, COVER);
            lv_obj_set_pos(t->name, 0, COVER + 10);
            lv_obj_add_flag(t->tile, LV_OBJ_FLAG_HIDDEN);
        }
    }

    footer = ui_one_line(screen, &instrument_24, 0xb4b1c2, WIDTH);
    lv_obj_set_pos(footer, LEFT, 650);

    lv_timer_create(tick, 1000, NULL);
}
