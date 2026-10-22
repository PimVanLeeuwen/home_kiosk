/* The Home panel's music (plan.md M18): the four favourites as a list of rows
 * with small covers, to start with a tap (on the device that plays, else the
 * living room's Apple TV, woken when needed), where they would play, and what
 * played last with its cover. Every line is one line, cut with an ellipsis. */

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
#define TOP 92
#define ROW_H 104
#define ROW_GAP 8
#define ART 96 /* the hub's "thumb" covers */
#define LAST_TOP 548

typedef struct {
    lv_obj_t *art, *image;
    picture_t showing;
    lv_image_dsc_t dsc;
} art_t;

static lv_obj_t *label_device, *divider, *last_box, *last_heading, *last_title, *last_subtitle;
static art_t last_art;
static struct {
    lv_obj_t *row, *name;
    art_t art;
} rows[DESK_FAVOURITES];
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

/* One line that ends in an ellipsis: without a fixed height a label wraps. */
static lv_obj_t *one_line(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = text(parent, font, colour);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_height(label, lv_font_get_line_height(font));
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

static void art_create(art_t *art, lv_obj_t *parent)
{
    art->art = plain(parent);
    lv_obj_set_size(art->art, ART, ART);
    lv_obj_set_style_radius(art->art, 14, 0);
    lv_obj_set_style_clip_corner(art->art, true, 0);
    lv_obj_set_style_bg_opa(art->art, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(art->art, lv_color_hex(0x1a1920), 0);
    art->image = lv_image_create(art->art);
    lv_obj_center(art->image);
    lv_obj_add_flag(art->image, LV_OBJ_FLAG_HIDDEN);
}

static void take_cover(int slot, art_t *art)
{
    picture_t fresh;
    if (!pictures_take(slot, &fresh)) {
        return;
    }
    picture_t old = art->showing;
    art->showing = fresh;
    if (fresh.pixels) {
        art->dsc = (lv_image_dsc_t){
            .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_RGB888, .w = fresh.width,
                       .h = fresh.height, .stride = fresh.width * 3},
            .data_size = fresh.width * fresh.height * 3,
            .data = fresh.pixels,
        };
        lv_image_set_src(art->image, &art->dsc);
        lv_image_cache_drop(&art->dsc);
    }
    lv_obj_set_flag(art->image, LV_OBJ_FLAG_HIDDEN, fresh.pixels == NULL);
    heap_caps_free(old.pixels);
}

static void on_row(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    if (i >= shown.count) {
        return;
    }
    char what[24];
    snprintf(what, sizeof what, "favourite/%d", shown.favourites[i].position);
    if (actions_music(what)) {
        /* The row lights up in the cover's colour: it may take the Apple TV a
         * few seconds to wake. */
        lv_obj_set_style_bg_opa(rows[i].row, 70, 0);
    }
}

static void tick(lv_timer_t *timer)
{
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        take_cover(PICTURE_FAVOURITE + i, &rows[i].art);
    }
    take_cover(PICTURE_LAST, &last_art);
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
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        lv_obj_set_flag(rows[i].row, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i < shown.count) {
            lv_color_t colour = lv_color_hex(shown.favourites[i].colour);
            lv_label_set_text(rows[i].name, shown.favourites[i].name);
            lv_obj_set_style_bg_color(rows[i].row, colour, 0);
            lv_obj_set_style_bg_opa(rows[i].row, 0, 0);
            lv_obj_set_style_bg_color(rows[i].art.art, colour, 0); /* until the cover is in */
        }
    }
    bool any = shown.last_title[0] != '\0';
    lv_obj_set_flag(divider, LV_OBJ_FLAG_HIDDEN, !any);
    lv_obj_set_flag(last_box, LV_OBJ_FLAG_HIDDEN, !any);
    upper(caps, sizeof caps, shown.last_heading);
    lv_label_set_text(last_heading, caps);
    lv_label_set_text(last_title, shown.last_title);
    lv_label_set_text(last_subtitle, shown.last_subtitle);
    lv_obj_set_flag(last_subtitle, LV_OBJ_FLAG_HIDDEN, shown.last_subtitle[0] == '\0');
    lv_obj_set_flag(last_art.art, LV_OBJ_FLAG_HIDDEN, !shown.has_last_cover);
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

    /* The favourites: cover, name, play; the whole row is the button. */
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        lv_obj_t *row = rows[i].row = plain(screen);
        lv_obj_set_size(row, WIDTH, ROW_H);
        lv_obj_set_pos(row, LEFT, TOP + i * (ROW_H + ROW_GAP));
        lv_obj_set_style_radius(row, 20, 0);
        lv_obj_set_style_pad_all(row, (ROW_H - ART) / 2, 0);
        lv_obj_set_style_pad_right(row, 16, 0);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(row, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(row, 24, 0);
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_add_event_cb(row, on_row, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        art_create(&rows[i].art, row);

        rows[i].name = one_line(row, &instrument_28_bold, 0xffffff);
        lv_obj_set_flex_grow(rows[i].name, 1);

        lv_obj_t *play = plain(row);
        lv_obj_set_size(play, 64, 64);
        lv_obj_set_style_radius(play, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(play, 235, 0);
        lv_obj_set_style_bg_color(play, lv_color_white(), 0);
        lv_obj_t *icon = icon_create(play, ICON_PLAY, 28, 0x121118);
        lv_obj_center(icon);
        lv_obj_add_flag(row, LV_OBJ_FLAG_HIDDEN);
    }

    /* What played last (or plays now): its cover, then heading, title and artist. */
    divider = plain(screen);
    lv_obj_set_size(divider, WIDTH, 1);
    lv_obj_set_pos(divider, LEFT, LAST_TOP);
    lv_obj_set_style_bg_opa(divider, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(divider, lv_color_hex(0x2a2833), 0);
    lv_obj_add_flag(divider, LV_OBJ_FLAG_HIDDEN);

    last_box = plain(screen);
    lv_obj_set_size(last_box, WIDTH, ART);
    lv_obj_set_pos(last_box, LEFT, LAST_TOP + 24);
    lv_obj_set_flex_flow(last_box, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(last_box, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(last_box, 24, 0);
    lv_obj_add_flag(last_box, LV_OBJ_FLAG_HIDDEN);
    art_create(&last_art, last_box);

    lv_obj_t *words = plain(last_box);
    lv_obj_set_height(words, LV_SIZE_CONTENT);
    lv_obj_set_flex_grow(words, 1);
    lv_obj_set_flex_flow(words, LV_FLEX_FLOW_COLUMN);
    last_heading = one_line(words, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(last_heading, 2, 0);
    last_title = one_line(words, &instrument_28_bold, 0xffffff);
    last_subtitle = one_line(words, &instrument_24, 0xb4b1c2);
    lv_obj_set_width(last_heading, LV_PCT(100));
    lv_obj_set_width(last_title, LV_PCT(100));
    lv_obj_set_width(last_subtitle, LV_PCT(100));

    lv_timer_create(tick, 1000, NULL);
}
