/* The Home panel's music (plan.md M18), as in the desk panels mockup: the four
 * favourites as tiles with their covers, to start with a tap (on the device
 * that plays, else the living room's Apple TV, woken when needed), where they
 * would play, and what played last. */

#include "screen_music.h"

#include <stdio.h>
#include <string.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "icons.h"
#include "lvgl.h"
#include "pictures.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define WIDTH 648
#define TILE_W 318
#define TILE_H 256
#define TOP 84

static lv_obj_t *label_device, *last;
static struct {
    lv_obj_t *tile, *image, *name;
    picture_t showing;
    lv_image_dsc_t dsc;
} tiles[DESK_FAVOURITES];
EXT_RAM_BSS_ATTR static desk_music_t shown; /* off the LVGL task's small stack */

static lv_obj_t *plain(lv_obj_t *parent)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_label_set_text(label, "");
    return label;
}

static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

static void on_tile(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    if (i >= shown.count) {
        return;
    }
    char what[24];
    snprintf(what, sizeof what, "favourite/%d", shown.favourites[i].position);
    if (actions_music(what)) {
        /* A moment of light around the tile: it may take the Apple TV a few
         * seconds to wake. */
        lv_obj_set_style_border_opa(tiles[i].tile, LV_OPA_COVER, 0);
    }
}

static void take_cover(int i)
{
    picture_t fresh;
    if (!pictures_take(PICTURE_FAVOURITE + i, &fresh)) {
        return;
    }
    picture_t old = tiles[i].showing;
    tiles[i].showing = fresh;
    if (fresh.pixels) {
        tiles[i].dsc = (lv_image_dsc_t){
            .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_RGB888, .w = fresh.width,
                       .h = fresh.height, .stride = fresh.width * 3},
            .data_size = fresh.width * fresh.height * 3,
            .data = fresh.pixels,
        };
        lv_image_set_src(tiles[i].image, &tiles[i].dsc);
        lv_image_cache_drop(&tiles[i].dsc);
    }
    lv_obj_set_flag(tiles[i].image, LV_OBJ_FLAG_HIDDEN, fresh.pixels == NULL);
    heap_caps_free(old.pixels);
}

static void tick(lv_timer_t *timer)
{
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        take_cover(i);
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
    upper(caps, sizeof caps, shown.device);
    lv_label_set_text(label_device, caps);
    lv_obj_set_flag(lv_obj_get_parent(label_device), LV_OBJ_FLAG_HIDDEN, shown.device[0] == '\0');
    lv_label_set_text(last, shown.last);
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        lv_obj_set_flag(tiles[i].tile, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i < shown.count) {
            lv_label_set_text(tiles[i].name, shown.favourites[i].name);
            lv_obj_set_style_bg_color(tiles[i].tile, lv_color_hex(shown.favourites[i].colour), 0);
            lv_obj_set_style_border_color(tiles[i].tile, lv_color_hex(shown.favourites[i].colour), 0);
            lv_obj_set_style_border_opa(tiles[i].tile, 0, 0);
        }
    }
}

void screen_music_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *header = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "MUSIC");
    lv_obj_set_pos(header, LEFT, 30);
    lv_obj_t *pill = plain(screen);
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
    label_device = text(pill, &instrument_24, 0xe6e3ef);
    lv_obj_set_style_text_letter_space(label_device, 1, 0);

    for (int i = 0; i < DESK_FAVOURITES; i++) {
        lv_obj_t *tile = tiles[i].tile = plain(screen);
        lv_obj_set_size(tile, TILE_W, TILE_H);
        lv_obj_set_pos(tile, LEFT + (i % 2) * (TILE_W + 12), TOP + (i / 2) * (TILE_H + 12));
        lv_obj_set_style_radius(tile, 24, 0);
        lv_obj_set_style_clip_corner(tile, true, 0);
        lv_obj_set_style_bg_opa(tile, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(tile, 4, 0);
        lv_obj_add_flag(tile, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_add_event_cb(tile, on_tile, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        tiles[i].image = lv_image_create(tile);
        lv_obj_center(tiles[i].image);
        lv_obj_add_flag(tiles[i].image, LV_OBJ_FLAG_HIDDEN);

        /* A dark fade under the name, so it reads on any cover. */
        lv_obj_t *fade = plain(tile);
        lv_obj_set_size(fade, TILE_W, 130);
        lv_obj_align(fade, LV_ALIGN_BOTTOM_MID, 0, 0);
        lv_obj_set_style_bg_opa(fade, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(fade, lv_color_black(), 0);
        lv_obj_set_style_bg_grad_color(fade, lv_color_black(), 0);
        lv_obj_set_style_bg_grad_dir(fade, LV_GRAD_DIR_VER, 0);
        lv_obj_set_style_bg_main_opa(fade, 0, 0);
        lv_obj_set_style_bg_grad_opa(fade, 210, 0);

        tiles[i].name = text(tile, &instrument_28_bold, 0xffffff);
        lv_label_set_long_mode(tiles[i].name, LV_LABEL_LONG_DOT);
        lv_obj_set_width(tiles[i].name, TILE_W - 40);
        lv_obj_align(tiles[i].name, LV_ALIGN_BOTTOM_LEFT, 20, -18);

        lv_obj_t *play = plain(tile);
        lv_obj_set_size(play, 56, 56);
        lv_obj_align(play, LV_ALIGN_TOP_RIGHT, -16, 16);
        lv_obj_set_style_radius(play, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(play, 235, 0);
        lv_obj_set_style_bg_color(play, lv_color_white(), 0);
        lv_obj_t *icon = icon_create(play, ICON_PLAY, 26, 0x121118);
        lv_obj_center(icon);
        lv_obj_add_flag(tile, LV_OBJ_FLAG_HIDDEN);
    }

    last = text(screen, &instrument_24, 0xb4b1c2);
    lv_label_set_long_mode(last, LV_LABEL_LONG_DOT);
    lv_obj_set_width(last, WIDTH);
    lv_obj_set_pos(last, LEFT, TOP + 2 * TILE_H + 12 + 22);

    lv_timer_create(tick, 1000, NULL);
}
