/* The Now panel's train screen (plan.md M20), as in the desk panels mockup and
 * the hub's train card: the departure in a labelled box (so it never reads as
 * the clock), the status large in its colour, how long until it leaves and
 * from which platform, a ring that empties over the last hour, and the route as a line.
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
#include "arrive.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define WIDTH 648
#define RING 196
#define ROUTE_TOP 512 /* the route's band, clear of the page dots */
#define ROUTE_H 170
#define NAME_ROW 34    /* the second row of names, with more than four stops */
#define LINE_Y 62      /* the line, inside the band */
#define DOT_INSET 11

static const uint32_t TONES[] = {0x5fd39c, 0xf0bd5a, 0xff6b6b}; /* up, warn, down */

static lv_obj_t *glow, *title, *column, *time_was, *time_now, *status, *sub_row, *sub, *platform_was, *platform;
static lv_obj_t *ring, *ring_number, *ring_label, *box, *box_label, *box_main, *box_more, *route;
EXT_RAM_BSS_ATTR static desk_train_t shown;
static int shown_minutes = -2;

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

/* A stop's name as shown: with more than four stops "Centraal" is written "C.", as NS does. */
static void stop_name(char *to, size_t size, const char *full, bool short_form)
{
    const char *centraal = short_form ? strstr(full, " Centraal") : NULL;
    if (centraal) {
        snprintf(to, size, "%.*s C.%s", (int)(centraal - full), full, centraal + 9);
    } else {
        snprintf(to, size, "%s", full);
    }
}

/* The width of the longest word in a name, so a wrapped name never breaks inside one. */
static int longest_word(const char *name)
{
    int widest = 0;
    for (const char *start = name; *start;) {
        const char *end = strchr(start, ' ');
        size_t length = end ? (size_t)(end - start) : strlen(start);
        int width = lv_text_get_width(start, length, &instrument_24, 0) + 2;
        widest = width > widest ? width : widest;
        start = end ? end + 1 : start + length;
    }
    return widest;
}

/* The route as a line across the foot of the screen (plan.md M27, L): a dot per stop, the
 * time above and the name below; you board at the first, lit, and the line fades from the
 * train's colour toward the end. Dimmed when the train does not run.
 *
 * The names are measured: where you board and where you get off keep their full name (up to
 * 40% of the width), the stops between take the room that is left, as near their dot as it
 * allows. Up to four stops a name may take two lines; with more they take turns in two rows. */
static void build_route(void)
{
    lv_obj_clean(route);
    lv_obj_set_style_opa(route, shown.gone ? 100 : LV_OPA_COVER, 0);
    int n = shown.stop_count;
    uint32_t tone = TONES[shown.tone];
    int span = WIDTH - 2 * DOT_INSET;
    lv_obj_t *line = ui_plain(route);
    lv_obj_set_pos(line, LEFT + DOT_INSET, LINE_Y - 2);
    lv_obj_set_size(line, span, 4);
    lv_obj_set_style_radius(line, 2, 0);
    lv_obj_set_style_bg_opa(line, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(line, lv_color_hex(tone), 0);
    lv_obj_set_style_bg_grad_color(line, lv_color_hex(0x3a3746), 0);
    lv_obj_set_style_bg_grad_dir(line, LV_GRAD_DIR_HOR, 0);

    lv_obj_t *light = lv_image_create(route); /* where you board */
    lv_image_set_src(light, &glow_round);
    lv_obj_set_pos(light, LEFT + DOT_INSET - 80, LINE_Y - 80);
    lv_obj_set_style_image_recolor(light, lv_color_hex(tone), 0);
    lv_obj_set_style_image_recolor_opa(light, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(light, 70, 0);

    bool rows = n > 4;
    int x[DESK_TRAIN_STOPS], left[DESK_TRAIN_STOPS], width[DESK_TRAIN_STOPS];
    char names[DESK_TRAIN_STOPS][40];
    for (int i = 0; i < n; i++) {
        x[i] = LEFT + DOT_INSET + (n > 1 ? i * span / (n - 1) : 0);
        stop_name(names[i], sizeof names[i], shown.stops[i].name, rows);
    }
    /* The ends first, at their dots; in one row they may wrap too, but never narrower than
     * their longest word. */
    int column = n > 1 ? span / (n - 1) : span;
    for (int i = 0; i < n; i += n > 1 ? n - 1 : 1) {
        int natural = lv_text_get_width(names[i], strlen(names[i]), &instrument_24, 0) + 2;
        int cap = WIDTH * 2 / 5;
        if (!rows) {
            int word = longest_word(names[i]);
            cap = column * 2 / 3 > word ? column * 2 / 3 : word;
        }
        width[i] = n == 1 ? WIDTH : natural < cap ? natural : cap;
        left[i] = i == 0 ? x[i] - DOT_INSET : x[i] + DOT_INSET - width[i];
    }
    /* Then the stops between, in the room up to their neighbours in the same row. */
    int step = rows ? 2 : 1;
    for (int i = 1; i < n - 1; i++) {
        int before = i - step, after = i + step;
        int from = before < 0 ? LEFT : before == 0 ? left[0] + width[0] + 12 : (x[before] + x[i]) / 2 + 6;
        int to = after > n - 1 ? LEFT + WIDTH : after == n - 1 ? left[n - 1] - 12 : (x[i] + x[after]) / 2 - 6;
        int natural = lv_text_get_width(names[i], strlen(names[i]), &instrument_24, 0) + 2;
        int room = to - from;
        width[i] = natural < room ? natural : room;
        int at = x[i] - width[i] / 2;
        left[i] = at < from ? from : at + width[i] > to ? to - width[i] : at;
    }

    for (int i = 0; i < n; i++) {
        bool first = i == 0, last = i == n - 1 && n > 1;
        bool skipped = shown.stops[i].cancelled;
        int size = first || last ? 22 : 16;
        lv_obj_t *dot = ui_plain(route);
        lv_obj_set_size(dot, size, size);
        lv_obj_set_pos(dot, x[i] - size / 2, LINE_Y - size / 2);
        lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(dot, lv_color_hex(first ? 0xf1eff7 : 0x000000), 0);
        lv_obj_set_style_border_width(dot, first ? 0 : 3, 0);
        lv_obj_set_style_border_color(dot, lv_color_hex(skipped ? 0x4a4757 : last ? 0xf1eff7 : 0x8f80ff), 0);

        lv_text_align_t align = first ? LV_TEXT_ALIGN_LEFT : last ? LV_TEXT_ALIGN_RIGHT : LV_TEXT_ALIGN_CENTER;
        /* The time sits over its dot, the ends at their dot's edge. */
        lv_obj_t *at = ui_text(route, &instrument_24, shown.stops[i].shifted ? 0xf0bd5a : first ? tone : 0xb4b1c2);
        lv_label_set_text(at, shown.stops[i].time);
        lv_obj_update_layout(at);
        int time_w = lv_obj_get_width(at);
        lv_obj_set_pos(at, first ? x[i] - DOT_INSET : last ? x[i] + DOT_INSET - time_w : x[i] - time_w / 2, LINE_Y - 50);

        lv_obj_t *name = ui_text(route, &instrument_24, skipped ? 0x6f6c7d : first || last ? 0xf1eff7 : 0xb4b1c2);
        lv_label_set_long_mode(name, LV_LABEL_LONG_DOT);
        lv_obj_set_size(name, width[i], (rows ? 1 : 2) * lv_font_get_line_height(&instrument_24));
        lv_obj_set_style_text_align(name, align, 0);
        lv_label_set_text(name, names[i]);
        lv_obj_set_pos(name, left[i], LINE_Y + 20 + (rows && i % 2 ? NAME_ROW : 0));
        if (skipped) {
            lv_obj_set_style_text_decor(at, LV_TEXT_DECOR_STRIKETHROUGH, 0);
            lv_obj_set_style_text_decor(name, LV_TEXT_DECOR_STRIKETHROUGH, 0);
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

/* The box goes below what the left column needs; the route keeps the foot of the screen
 * and is left out when the box needs its place. */
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
    bool fits = shown.stop_count > 0 && ROUTE_TOP >= below;
    lv_obj_set_flag(route, LV_OBJ_FLAG_HIDDEN, !fits);
    if (fits) {
        build_route();
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
        ui_upper(caps, sizeof caps, now.title);
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

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 24);

    column = ui_plain(screen);
    lv_obj_set_pos(column, LEFT, 84);
    lv_obj_set_size(column, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(column, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(column, 10, 0);

    lv_obj_t *label = ui_text(column, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(label, 2, 0);
    lv_label_set_text(label, "DEPARTURE");

    /* The departure in a box, so it never reads as the clock. */
    lv_obj_t *time_box = ui_plain(column);
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
    time_was = ui_text(time_box, &instrument_40, 0x6f6c7d);
    lv_obj_set_style_text_decor(time_was, LV_TEXT_DECOR_STRIKETHROUGH, 0);
    time_now = ui_text(time_box, &instrument_time, 0xf1eff7);

    status = ui_text(column, &instrument_52_bold, TONES[0]);
    lv_label_set_long_mode(status, LV_LABEL_LONG_WRAP);

    /* "Leaves in 34 min from platform" and the platform as a pill; a changed
     * platform shows the old one struck through and the new one in amber. */
    sub_row = ui_plain(column);
    lv_obj_set_height(sub_row, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(sub_row, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(sub_row, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(sub_row, 10, 0);
    lv_obj_set_style_pad_row(sub_row, 6, 0);
    sub = ui_text(sub_row, &instrument_24, 0xb4b1c2);
    lv_label_set_long_mode(sub, LV_LABEL_LONG_WRAP);
    platform_was = ui_text(sub_row, &instrument_24, 0x6f6c7d);
    lv_obj_set_style_text_decor(platform_was, LV_TEXT_DECOR_STRIKETHROUGH, 0);
    platform = ui_text(sub_row, &instrument_28_bold, 0xf1eff7);
    lv_obj_set_style_bg_opa(platform, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(platform, 8, 0);
    lv_obj_set_style_pad_hor(platform, 10, 0);
    lv_obj_set_style_pad_ver(platform, 2, 0);
    lv_obj_set_style_border_color(platform, lv_color_hex(0xf0bd5a), 0);

    /* Minutes to go: a ring that empties over the last hour. */
    ring = lv_arc_create(screen);
    arrive_sweep(ring);
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
    ring_number = ui_text(ring, &instrument_52_bold, 0xf1eff7);
    lv_obj_align(ring_number, LV_ALIGN_CENTER, 0, -12);
    ring_label = ui_text(ring, &instrument_24, 0xb4b1c2);
    lv_obj_align(ring_label, LV_ALIGN_CENTER, 0, 34);

    /* The next direct train, or a disruption on the route. */
    box = ui_plain(screen);
    lv_obj_set_pos(box, LEFT, 400);
    lv_obj_set_size(box, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(box, 18, 0);
    lv_obj_set_style_pad_ver(box, 12, 0);
    lv_obj_set_style_radius(box, 16, 0);
    lv_obj_set_style_border_width(box, 2, 0);
    lv_obj_set_style_bg_opa(box, 14, 0);
    lv_obj_set_flex_flow(box, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(box, 4, 0);
    box_label = ui_text(box, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(box_label, 2, 0);
    box_main = ui_text(box, &instrument_40, 0xffffff);
    /* NS's titles can list several stretches: wrap them inside the box. */
    lv_label_set_long_mode(box_main, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(box_main, WIDTH - 40);
    box_more = ui_text(box, &instrument_24, 0xb4b1c2);
    lv_label_set_long_mode(box_more, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(box_more, WIDTH - 40);
    lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);

    route = ui_plain(screen);
    lv_obj_set_pos(route, 0, ROUTE_TOP);
    lv_obj_set_size(route, 720, ROUTE_H);
    arrive_draw_in(route, 720, ROUTE_H);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
