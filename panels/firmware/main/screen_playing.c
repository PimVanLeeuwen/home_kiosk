/* The Home panel's Now Playing (plan.md M18), as in the desk panels mockup: the
 * cover with a record behind it, the title and artist, how far it is, and the
 * controls; the screen is lit in the cover's colour. The values come from the
 * hub (app/desk_home.py), the cover from pictures.c; the progress moves on with
 * the panel's own clock between the hub's answers. */

#include "screen_playing.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "icons.h"
#include "lvgl.h"
#include "pictures.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define WIDTH 648
#define COVER 288
#define RECORD 270

static lv_obj_t *sky, *halo, *cover, *label_device, *title, *subtitle, *progress, *elapsed, *length;
static lv_obj_t *play_button, *play_icon, *record_label;
static ui_picture_t cover_picture;
EXT_RAM_BSS_ATTR static desk_playing_t shown; /* off the LVGL task's small stack */

static void minutes(char *into, size_t size, int64_t ms)
{
    unsigned s = (unsigned)(ms / 1000) % 36000; /* under ten hours: always fits */
    snprintf(into, size, "%u:%02u", s / 60, s % 60);
}

/* Where the track is now: what the hub read, moved on by the time since. */
static int64_t position(void)
{
    if (!shown.playing || shown.at <= 0) {
        return shown.progress_ms;
    }
    struct timeval tv;
    gettimeofday(&tv, NULL);
    double since = tv.tv_sec + tv.tv_usec / 1e6 - shown.at;
    int64_t at = shown.progress_ms + (int64_t)(since > 0 ? since * 1000 : 0);
    return at < shown.duration_ms ? at : shown.duration_ms;
}

static void show_progress(void)
{
    int64_t at = position();
    lv_bar_set_value(progress, shown.duration_ms ? (int32_t)(at * 1000 / shown.duration_ms) : 0, LV_ANIM_OFF);
    char text_at[16], text_length[16];
    minutes(text_at, sizeof text_at, at);
    minutes(text_length, sizeof text_length, shown.duration_ms);
    lv_label_set_text(elapsed, text_at);
    lv_label_set_text(length, text_length);
}

static void on_play(lv_event_t *event)
{
    if (actions_music(shown.playing ? "pause" : "play")) {
        shown.playing = !shown.playing; /* at once; the hub's answer follows */
        icon_set(play_icon, shown.playing ? ICON_PAUSE : ICON_PLAY);
    }
}

static void on_skip(lv_event_t *event)
{
    actions_music((const char *)lv_event_get_user_data(event));
}

static void tick(lv_timer_t *timer)
{
    ui_take_picture(PICTURE_PLAYING, &cover_picture);
    static uint32_t version;
    if (desk_playing_version() != version) {
        shown = desk_playing();
        version = shown.version;
        if (shown.present) {
            lv_label_set_text(title, shown.title);
            lv_label_set_text(subtitle, shown.subtitle);
            char caps[64];
            ui_upper(caps, sizeof caps, shown.device);
            lv_label_set_text(label_device, caps);
            lv_obj_set_flag(lv_obj_get_parent(label_device), LV_OBJ_FLAG_HIDDEN, shown.device[0] == '\0');
            lv_obj_set_style_image_recolor(sky, lv_color_hex(shown.colour), 0);
            lv_obj_set_style_image_recolor(halo, lv_color_hex(shown.colour), 0);
            lv_obj_set_style_bg_color(cover, lv_color_hex(shown.colour), 0);
            lv_obj_set_style_bg_color(record_label, lv_color_hex(shown.colour), 0);
            icon_set(play_icon, shown.playing ? ICON_PAUSE : ICON_PLAY);
        }
    }
    if (shown.present) {
        show_progress();
    }
}

static lv_obj_t *round_button(lv_obj_t *parent, int size, uint32_t fill, lv_opa_t opa)
{
    lv_obj_t *button = ui_plain(parent);
    lv_obj_set_size(button, size, size);
    lv_obj_set_style_radius(button, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(button, lv_color_hex(fill), 0);
    lv_obj_set_style_bg_opa(button, opa, 0);
    lv_obj_add_flag(button, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_set_ext_click_area(button, 12);
    return button;
}

void screen_playing_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Light in the cover's colour from the top, and a glow behind the cover. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 90, 0);
    halo = lv_image_create(screen);
    lv_image_set_src(halo, &glow_round);
    lv_image_set_scale(halo, 256 * 3);
    lv_obj_set_pos(halo, LEFT + COVER / 2 - 80, 36 + COVER / 2 - 80);
    lv_obj_set_style_image_recolor_opa(halo, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(halo, 80, 0);

    /* The record peeking out behind the cover. */
    lv_obj_t *record = ui_plain(screen);
    lv_obj_set_size(record, RECORD, RECORD);
    lv_obj_set_pos(record, LEFT + COVER - RECORD / 2, 36 + (COVER - RECORD) / 2);
    lv_obj_set_style_radius(record, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(record, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(record, lv_color_hex(0x0e0d12), 0);
    lv_obj_set_style_border_width(record, 2, 0);
    lv_obj_set_style_border_color(record, lv_color_hex(0x2c2a33), 0);
    for (int r = 210; r >= 120; r -= 30) {
        lv_obj_t *groove = ui_plain(record);
        lv_obj_set_size(groove, r, r);
        lv_obj_center(groove);
        lv_obj_set_style_radius(groove, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(groove, 1, 0);
        lv_obj_set_style_border_color(groove, lv_color_hex(0x24222b), 0);
    }
    record_label = ui_plain(record);
    lv_obj_set_size(record_label, 74, 74);
    lv_obj_center(record_label);
    lv_obj_set_style_radius(record_label, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(record_label, LV_OPA_COVER, 0);

    cover = ui_plain(screen);
    lv_obj_set_size(cover, COVER, COVER);
    lv_obj_set_pos(cover, LEFT, 36);
    lv_obj_set_style_radius(cover, 22, 0);
    lv_obj_set_style_clip_corner(cover, true, 0);
    lv_obj_set_style_bg_opa(cover, LV_OPA_COVER, 0);
    cover_picture.image = lv_image_create(cover);
    lv_obj_add_flag(cover_picture.image, LV_OBJ_FLAG_HIDDEN);

    /* Where it plays, as a pill at the top right. */
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
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 36);
    label_device = ui_text(pill, &instrument_24, 0xe6e3ef);
    lv_obj_set_style_text_letter_space(label_device, 1, 0);

    /* Title (two lines at most) and artist (one), stacked, so a short title keeps
     * its artist close. */
    lv_obj_t *words = ui_plain(screen);
    lv_obj_set_pos(words, LEFT, 344);
    lv_obj_set_size(words, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(words, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(words, 8, 0);
    title = ui_text(words, &instrument_52_bold, 0xffffff);
    lv_label_set_long_mode(title, LV_LABEL_LONG_DOT);
    lv_obj_set_width(title, WIDTH);
    lv_obj_set_style_max_height(title, 124, 0);
    subtitle = ui_one_line(words, &instrument_24, 0xc9c6d4, WIDTH); /* not into the progress bar */

    progress = lv_bar_create(screen);
    lv_obj_set_size(progress, WIDTH, 8);
    lv_obj_set_pos(progress, LEFT, 522);
    lv_bar_set_range(progress, 0, 1000);
    lv_obj_set_style_bg_color(progress, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(progress, 40, LV_PART_MAIN);
    lv_obj_set_style_bg_color(progress, lv_color_white(), LV_PART_INDICATOR);
    lv_obj_set_style_radius(progress, 4, LV_PART_MAIN);
    lv_obj_set_style_radius(progress, 4, LV_PART_INDICATOR);
    elapsed = ui_text(screen, &instrument_24, 0xb4b1c2);
    lv_obj_set_pos(elapsed, LEFT, 538);
    length = ui_text(screen, &instrument_24, 0xb4b1c2);
    lv_obj_align(length, LV_ALIGN_TOP_RIGHT, -LEFT, 538);

    /* Previous, play or pause, next. */
    play_button = round_button(screen, 104, 0xffffff, LV_OPA_COVER);
    lv_obj_align(play_button, LV_ALIGN_TOP_MID, 0, 578);
    lv_obj_add_event_cb(play_button, on_play, LV_EVENT_CLICKED, NULL);
    play_icon = icon_create(play_button, ICON_PAUSE, 44, 0x121118);
    lv_obj_center(play_icon);
    const char *skips[] = {"previous", "next"};
    for (int i = 0; i < 2; i++) {
        lv_obj_t *button = round_button(screen, 84, 0xffffff, 0);
        lv_obj_align(button, LV_ALIGN_TOP_MID, i ? 170 : -170, 588);
        lv_obj_add_event_cb(button, on_skip, LV_EVENT_CLICKED, (void *)skips[i]);
        lv_obj_t *icon = icon_create(button, i ? ICON_NEXT : ICON_PREVIOUS, 40, 0xffffff);
        lv_obj_center(icon);
    }

    lv_timer_create(tick, 500, NULL);
}
