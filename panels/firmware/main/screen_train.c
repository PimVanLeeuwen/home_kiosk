/* The Now panel's train screen (plan.md M20), as in the desk panels mockup and
 * the hub's train card: the departure in a labelled box (so it never reads as
 * the clock), the status large in its colour, how long until it leaves and
 * from which platform, a ring that empties over the last hour, and the route.
 * When it does not run, the next direct train; a disruption on the route as a
 * note. The values come worded from the hub (app/desk_train.py); the minutes
 * count down on the panel's own clock. */

#include "screen_train.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define WIDTH 648
#define RING 196
#define ROW 40
#define BOTTOM 700

static const uint32_t TONES[] = {0x5fd39c, 0xf0bd5a, 0xff6b6b}; /* up, warn, down */

static lv_obj_t *glow, *title, *column, *time_was, *time_now, *status, *sub_row, *sub, *platform_was, *platform;
static lv_obj_t *ring, *ring_number, *ring_label, *box, *box_label, *box_main, *box_more, *route;
EXT_RAM_BSS_ATTR static desk_train_t shown;
static int shown_minutes = -2;

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_label_set_text(label, "");
    return label;
}

static lv_obj_t *plain(lv_obj_t *parent)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

/* Minutes until the followed train leaves, rounded up as the NS app does; -1
 * without a time to count to. */
static int minutes_to_go(void)
{
    struct timeval now;
    gettimeofday(&now, NULL);
    if (shown.leaves_at == 0 || now.tv_sec < 1700000000) {
        return -1;
    }
    int64_t left = shown.leaves_at - now.tv_sec;
    return left <= 0 ? 0 : (int)((left + 59) / 60);
}

static void set_minutes(int minutes)
{
    lv_obj_set_flag(ring, LV_OBJ_FLAG_HIDDEN, minutes < 0);
    lv_obj_set_flag(glow, LV_OBJ_FLAG_HIDDEN, minutes < 0); /* the light belongs to the ring */
    if (minutes >= 0) {
        lv_arc_set_value(ring, minutes > 60 ? 60 : minutes);
        lv_label_set_text_fmt(ring_number, "%d", minutes);
    }
    if (shown.sub[0] == '\0' && !shown.gone) {
        if (minutes < 0) {
            lv_label_set_text(sub, "Leaves from platform");
        } else if (minutes < 1) {
            lv_label_set_text(sub, "Leaves now from platform");
        } else {
            lv_label_set_text_fmt(sub, "Leaves in %d min from platform", minutes);
        }
    }
}

/* The route at the bottom: a dot per stop on a line, the time and the name;
 * the first stop with its platform. Dimmed when the train does not run. */
static void build_route(int top)
{
    lv_obj_clean(route);
    lv_obj_set_pos(route, 0, top);
    lv_obj_set_size(route, 720, shown.stop_count * ROW);
    lv_obj_set_style_opa(route, shown.gone ? 100 : LV_OPA_COVER, 0);
    uint32_t tone = TONES[shown.tone];
    if (shown.stop_count > 1) {
        lv_obj_t *line = plain(route);
        lv_obj_set_pos(line, LEFT + 6, ROW / 2);
        lv_obj_set_size(line, 3, (shown.stop_count - 1) * ROW);
        lv_obj_set_style_bg_opa(line, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(line, lv_color_hex(tone), 0);
        lv_obj_set_style_bg_grad_color(line, lv_color_hex(0x2a2833), 0);
        lv_obj_set_style_bg_grad_dir(line, LV_GRAD_DIR_VER, 0);
    }
    for (int i = 0; i < shown.stop_count; i++) {
        int y = i * ROW;
        lv_obj_t *dot = plain(route);
        lv_obj_set_size(dot, 15, 15);
        lv_obj_set_pos(dot, LEFT, y + ROW / 2 - 7);
        lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(dot, lv_color_hex(i == 0 ? 0xb4a9ff : 0x000000), 0);
        lv_obj_set_style_border_width(dot, 3, 0);
        lv_obj_set_style_border_color(dot, lv_color_hex(i == 0 ? 0xb4a9ff : 0x8f80ff), 0);

        bool skipped = shown.stops[i].cancelled;
        lv_obj_t *at = text(route, &instrument_24, shown.stops[i].shifted ? 0xf0bd5a : 0xb4b1c2);
        lv_label_set_text(at, shown.stops[i].time);
        lv_obj_set_pos(at, LEFT + 34, y + 8);
        lv_obj_t *name = text(route, &instrument_24, skipped ? 0x6f6c7d : 0xf1eff7);
        lv_label_set_text(name, shown.stops[i].name);
        lv_obj_set_pos(name, LEFT + 120, y + 8);
        if (skipped) {
            lv_obj_set_style_text_decor(at, LV_TEXT_DECOR_STRIKETHROUGH, 0);
            lv_obj_set_style_text_decor(name, LV_TEXT_DECOR_STRIKETHROUGH, 0);
        }
        if (i == 0 && shown.platform[0]) {
            lv_obj_t *track = text(route, &instrument_24, 0x8a8794);
            lv_label_set_text_fmt(track, "platform %s", shown.platform);
            lv_obj_align(track, LV_ALIGN_TOP_RIGHT, -LEFT, y + 8);
        }
    }
}

static void show_box(void)
{
    lv_obj_set_flag(box, LV_OBJ_FLAG_HIDDEN, !(shown.has_next || shown.has_notice));
    if (shown.has_next) {
        lv_obj_set_style_border_color(box, lv_color_white(), 0);
        lv_obj_set_style_border_opa(box, 40, 0);
        lv_obj_set_style_bg_color(box, lv_color_white(), 0);
        lv_label_set_text(box_label, "NEXT DIRECT TRAIN");
        lv_obj_set_style_text_font(box_main, &instrument_40, 0);
        lv_obj_set_style_text_color(box_main, lv_color_white(), 0);
        lv_label_set_text(box_main, shown.next_departure);
        lv_label_set_text_fmt(box_more, "platform %s  ·  arrives %s", shown.next_platform, shown.next_arrives);
    } else if (shown.has_notice) {
        lv_obj_set_style_border_color(box, lv_color_hex(0xf0bd5a), 0);
        lv_obj_set_style_border_opa(box, 90, 0);
        lv_obj_set_style_bg_color(box, lv_color_hex(0xf0bd5a), 0);
        lv_label_set_text(box_label, "ON THE ROUTE");
        lv_obj_set_style_text_font(box_main, &instrument_28_bold, 0);
        lv_obj_set_style_text_color(box_main, lv_color_hex(0xf0bd5a), 0);
        lv_label_set_text(box_main, shown.notice_title);
        lv_label_set_text(box_more, shown.notice_text);
    }
}

/* Boxes and route go below what the left column needs; the route sits at the
 * bottom when there is room, and is left out when a box needs its place. */
static void place(void)
{
    lv_obj_update_layout(column);
    int below = lv_obj_get_y(column) + lv_obj_get_height(column) + 24;
    if (!lv_obj_has_flag(ring, LV_OBJ_FLAG_HIDDEN)) {
        int ring_bottom = lv_obj_get_y(ring) + RING + 16;
        below = below > ring_bottom ? below : ring_bottom;
    }
    if (!lv_obj_has_flag(box, LV_OBJ_FLAG_HIDDEN)) {
        lv_obj_set_y(box, below);
        lv_obj_update_layout(box);
        below = lv_obj_get_y(box) + lv_obj_get_height(box) + 16;
    }
    int top = BOTTOM - shown.stop_count * ROW;
    bool fits = shown.stop_count > 0 && top >= below;
    lv_obj_set_flag(route, LV_OBJ_FLAG_HIDDEN, !fits);
    if (fits) {
        build_route(top);
    }
}

static void tick(lv_timer_t *timer)
{
    EXT_RAM_BSS_ATTR static desk_train_t now; /* off the LVGL task's small stack */
    now = desk_train();
    bool changed = now.version != shown.version;
    if (changed) {
        shown = now;
        if (!now.present) {
            return;
        }
        uint32_t tone = TONES[now.tone];
        char caps[64];
        upper(caps, sizeof caps, now.title);
        lv_label_set_text(title, caps);
        lv_obj_set_style_image_recolor(glow, lv_color_hex(tone), 0);

        lv_label_set_text(time_now, now.departure_now[0] ? now.departure_now : now.departure);
        lv_label_set_text(time_was, now.departure);
        lv_obj_set_flag(time_was, LV_OBJ_FLAG_HIDDEN, now.departure_now[0] == '\0');
        lv_obj_set_style_text_decor(time_now, now.gone ? LV_TEXT_DECOR_STRIKETHROUGH : LV_TEXT_DECOR_NONE, 0);
        lv_obj_set_style_text_color(time_now, lv_color_hex(now.gone ? 0x6f6c7d : 0xf1eff7), 0);

        lv_label_set_text(status, now.status);
        lv_obj_set_style_text_color(status, lv_color_hex(tone), 0);
        /* Without the ring (the evening before) the status may use the full width. */
        lv_obj_set_width(status, now.leaves_at ? WIDTH - RING - 24 : WIDTH);
        lv_obj_set_width(sub_row, now.leaves_at ? WIDTH - RING - 24 : WIDTH);
        if (now.sub[0]) {
            lv_label_set_text(sub, now.sub);
        }
        lv_obj_set_flag(platform, LV_OBJ_FLAG_HIDDEN, now.platform[0] == '\0');
        /* Alone (no platform pill), a long line wraps over the full width. */
        lv_obj_set_width(sub, now.platform[0] ? LV_SIZE_CONTENT : lv_pct(100));
        lv_label_set_text(platform, now.platform);
        bool moved = now.platform_was[0] != '\0';
        lv_obj_set_flag(platform_was, LV_OBJ_FLAG_HIDDEN, !moved);
        lv_label_set_text(platform_was, now.platform_was);
        lv_obj_set_style_bg_color(platform, lv_color_hex(moved ? 0x3a2f1a : 0x2a2833), 0);
        lv_obj_set_style_text_color(platform, lv_color_hex(moved ? 0xf0bd5a : 0xf1eff7), 0);
        lv_obj_set_style_border_width(platform, moved ? 2 : 0, 0);

        lv_obj_set_style_arc_color(ring, lv_color_hex(tone), LV_PART_INDICATOR);
        lv_label_set_text(ring_label, now.ring_label);
        show_box();
        shown_minutes = -2;
    }
    if (!shown.present) {
        return;
    }
    int minutes = minutes_to_go();
    if (minutes != shown_minutes) {
        set_minutes(minutes);
        shown_minutes = minutes;
        place();
    }
}

void screen_train_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Light in the colour of how the train is doing, behind the ring. */
    glow = lv_image_create(screen);
    lv_image_set_src(glow, &glow_round);
    lv_image_set_scale(glow, 256 * 520 / 160);
    lv_obj_set_pos(glow, 720 - LEFT - RING / 2 - 80, 84 + RING / 2 - 80);
    lv_obj_set_style_image_recolor_opa(glow, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(glow, 46, 0);

    title = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 24);

    column = plain(screen);
    lv_obj_set_pos(column, LEFT, 84);
    lv_obj_set_size(column, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(column, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(column, 10, 0);

    lv_obj_t *label = text(column, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(label, 2, 0);
    lv_label_set_text(label, "DEPARTURE");

    /* The departure in a box, so it never reads as the clock. */
    lv_obj_t *time_box = plain(column);
    lv_obj_set_size(time_box, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(time_box, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(time_box, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_hor(time_box, 20, 0);
    lv_obj_set_style_pad_ver(time_box, 6, 0);
    lv_obj_set_style_pad_column(time_box, 14, 0);
    lv_obj_set_style_radius(time_box, 16, 0);
    lv_obj_set_style_border_width(time_box, 2, 0);
    lv_obj_set_style_border_color(time_box, lv_color_white(), 0);
    lv_obj_set_style_border_opa(time_box, 50, 0);
    lv_obj_set_style_bg_color(time_box, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(time_box, 12, 0);
    time_was = text(time_box, &instrument_40, 0x6f6c7d);
    lv_obj_set_style_text_decor(time_was, LV_TEXT_DECOR_STRIKETHROUGH, 0);
    time_now = text(time_box, &instrument_time, 0xf1eff7);

    status = text(column, &instrument_52_bold, TONES[0]);
    lv_label_set_long_mode(status, LV_LABEL_LONG_WRAP);

    /* "Leaves in 34 min from platform" and the platform as a pill; a changed
     * platform shows the old one struck through and the new one in amber. */
    sub_row = plain(column);
    lv_obj_set_height(sub_row, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(sub_row, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(sub_row, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(sub_row, 10, 0);
    lv_obj_set_style_pad_row(sub_row, 6, 0);
    sub = text(sub_row, &instrument_24, 0xb4b1c2);
    lv_label_set_long_mode(sub, LV_LABEL_LONG_WRAP);
    platform_was = text(sub_row, &instrument_24, 0x6f6c7d);
    lv_obj_set_style_text_decor(platform_was, LV_TEXT_DECOR_STRIKETHROUGH, 0);
    platform = text(sub_row, &instrument_28_bold, 0xf1eff7);
    lv_obj_set_style_bg_opa(platform, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(platform, 8, 0);
    lv_obj_set_style_pad_hor(platform, 10, 0);
    lv_obj_set_style_pad_ver(platform, 2, 0);
    lv_obj_set_style_border_color(platform, lv_color_hex(0xf0bd5a), 0);

    /* Minutes to go: a ring that empties over the last hour. */
    ring = lv_arc_create(screen);
    lv_obj_remove_style(ring, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(ring, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_size(ring, RING, RING);
    lv_obj_set_pos(ring, 720 - LEFT - RING, 84);
    lv_arc_set_rotation(ring, 270);
    lv_arc_set_bg_angles(ring, 0, 360);
    lv_arc_set_range(ring, 0, 60);
    lv_obj_set_style_arc_width(ring, 14, LV_PART_MAIN);
    lv_obj_set_style_arc_width(ring, 14, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(ring, lv_color_hex(0x232129), LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(ring, true, LV_PART_INDICATOR);
    ring_number = text(ring, &instrument_52_bold, 0xf1eff7);
    lv_obj_align(ring_number, LV_ALIGN_CENTER, 0, -12);
    ring_label = text(ring, &instrument_24, 0xb4b1c2);
    lv_obj_align(ring_label, LV_ALIGN_CENTER, 0, 34);

    /* The next direct train, or a disruption on the route. */
    box = plain(screen);
    lv_obj_set_pos(box, LEFT, 400);
    lv_obj_set_size(box, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(box, 18, 0);
    lv_obj_set_style_pad_ver(box, 12, 0);
    lv_obj_set_style_radius(box, 16, 0);
    lv_obj_set_style_border_width(box, 2, 0);
    lv_obj_set_style_bg_opa(box, 14, 0);
    lv_obj_set_flex_flow(box, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(box, 4, 0);
    box_label = text(box, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(box_label, 2, 0);
    box_main = text(box, &instrument_40, 0xffffff);
    box_more = text(box, &instrument_24, 0xb4b1c2);
    lv_label_set_long_mode(box_more, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(box_more, WIDTH - 40);
    lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);

    route = plain(screen);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
