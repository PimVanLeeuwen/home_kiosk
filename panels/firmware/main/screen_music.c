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
#include "icons.h"
#include "lvgl.h"
#include "pictures.h"
#include "ui.h"

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
    lv_obj_t *art; /* the box, in the playlist's colour until its cover is in */
    ui_picture_t cover;
} art_t;

static lv_obj_t *label_device, *divider, *last_box, *last_heading, *last_title, *last_subtitle;
static art_t last_art;
static struct {
    lv_obj_t *row, *name;
    art_t art;
} rows[DESK_FAVOURITES];
EXT_RAM_BSS_ATTR static desk_music_t shown; /* off the LVGL task's small stack */

static void art_create(art_t *art, lv_obj_t *parent)
{
    art->art = ui_plain(parent);
    lv_obj_set_size(art->art, ART, ART);
    lv_obj_set_style_radius(art->art, 14, 0);
    lv_obj_set_style_clip_corner(art->art, true, 0);
    lv_obj_set_style_bg_opa(art->art, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(art->art, lv_color_hex(0x1a1920), 0);
    art->cover.image = lv_image_create(art->art);
    lv_obj_center(art->cover.image);
    lv_obj_add_flag(art->cover.image, LV_OBJ_FLAG_HIDDEN);
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
        ui_take_picture(PICTURE_FAVOURITE + i, &rows[i].art.cover);
    }
    ui_take_picture(PICTURE_LAST, &last_art.cover);
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
    ui_upper(caps, sizeof caps, shown.last_heading);
    lv_label_set_text(last_heading, caps);
    lv_label_set_text(last_title, shown.last_title);
    lv_label_set_text(last_subtitle, shown.last_subtitle);
    lv_obj_set_flag(last_subtitle, LV_OBJ_FLAG_HIDDEN, shown.last_subtitle[0] == '\0');
    lv_obj_set_flag(last_art.art, LV_OBJ_FLAG_HIDDEN, !shown.has_last_cover);
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

    /* The favourites: cover, name, play; the whole row is the button. */
    for (int i = 0; i < DESK_FAVOURITES; i++) {
        lv_obj_t *row = rows[i].row = ui_plain(screen);
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

        rows[i].name = ui_one_line(row, &instrument_28_bold, 0xffffff, 0);
        lv_obj_set_flex_grow(rows[i].name, 1);

        lv_obj_t *play = ui_plain(row);
        lv_obj_set_size(play, 64, 64);
        lv_obj_set_style_radius(play, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(play, 235, 0);
        lv_obj_set_style_bg_color(play, lv_color_white(), 0);
        lv_obj_t *icon = icon_create(play, ICON_PLAY, 28, 0x121118);
        lv_obj_center(icon);
        lv_obj_add_flag(row, LV_OBJ_FLAG_HIDDEN);
    }

    /* What played last (or plays now): its cover, then heading, title and artist. */
    divider = ui_plain(screen);
    lv_obj_set_size(divider, WIDTH, 1);
    lv_obj_set_pos(divider, LEFT, LAST_TOP);
    lv_obj_set_style_bg_opa(divider, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(divider, lv_color_hex(0x2a2833), 0);
    lv_obj_add_flag(divider, LV_OBJ_FLAG_HIDDEN);

    last_box = ui_plain(screen);
    lv_obj_set_size(last_box, WIDTH, ART);
    lv_obj_set_pos(last_box, LEFT, LAST_TOP + 24);
    lv_obj_set_flex_flow(last_box, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(last_box, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(last_box, 24, 0);
    lv_obj_add_flag(last_box, LV_OBJ_FLAG_HIDDEN);
    art_create(&last_art, last_box);

    lv_obj_t *words = ui_plain(last_box);
    lv_obj_set_height(words, LV_SIZE_CONTENT);
    lv_obj_set_flex_grow(words, 1);
    lv_obj_set_flex_flow(words, LV_FLEX_FLOW_COLUMN);
    last_heading = ui_one_line(words, &instrument_24, 0x8a8794, LV_PCT(100));
    lv_obj_set_style_text_letter_space(last_heading, 2, 0);
    last_title = ui_one_line(words, &instrument_28_bold, 0xffffff, LV_PCT(100));
    last_subtitle = ui_one_line(words, &instrument_24, 0xb4b1c2, LV_PCT(100));

    lv_timer_create(tick, 1000, NULL);
}
