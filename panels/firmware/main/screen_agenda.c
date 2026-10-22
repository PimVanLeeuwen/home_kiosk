/* The Now panel's calendar screen (plan.md M20), as in the desk panels mockup
 * and the hub's Today card: the event under way or the next one large, with a
 * ring counting its minutes down in its calendar's colour; the all-day events;
 * the day from 07:00 to 23:00 as a ribbon of coloured blocks with a now line;
 * then what comes later. The events come from the hub (app/desk_agenda.py);
 * which one is "now or next" follows the panel's own clock, minute by minute. */

#include "screen_agenda.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define WIDTH 648
#define RING 170
#define TEXT_X (LEFT + RING + 28)
#define DAY_FROM (7 * 60)
#define DAY_TO (23 * 60)
#define ROW 42
#define BOTTOM 700

static lv_obj_t *glow, *title, *count, *ring, *ring_number, *ring_label, *kicker, *event_title, *event_time;
static lv_obj_t *focus_text, *done, *chips, *ribbon, *later;
EXT_RAM_BSS_ATTR static desk_agenda_t shown; /* about 2 kB: in PSRAM, off the LVGL task's stack */
static int shown_minute = -1;

static lv_obj_t *dot(lv_obj_t *parent, int size, uint32_t colour)
{
    lv_obj_t *obj = ui_plain(parent);
    lv_obj_set_size(obj, size, size);
    lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(obj, lv_color_hex(colour), 0);
    return obj;
}

static int ribbon_x(int minute)
{
    minute = minute < DAY_FROM ? DAY_FROM : minute > DAY_TO ? DAY_TO : minute;
    return (minute - DAY_FROM) * WIDTH / (DAY_TO - DAY_FROM);
}

/* The event under way, else the next one; -1 once the day is done. */
static int focus_of(int64_t now, bool *under_way)
{
    for (int i = 0; i < shown.event_count; i++) {
        if (shown.events[i].start_at <= now && now < shown.events[i].end_at) {
            *under_way = true;
            return i;
        }
    }
    for (int i = 0; i < shown.event_count; i++) {
        if (shown.events[i].start_at > now) {
            *under_way = false;
            return i;
        }
    }
    return -1;
}

static int show_focus(int64_t now)
{
    bool under_way = false;
    int focus = focus_of(now, &under_way);
    lv_obj_set_flag(ring, LV_OBJ_FLAG_HIDDEN, focus < 0);
    lv_obj_set_flag(glow, LV_OBJ_FLAG_HIDDEN, focus < 0);
    lv_obj_set_flag(focus_text, LV_OBJ_FLAG_HIDDEN, focus < 0);
    lv_obj_set_flag(done, LV_OBJ_FLAG_HIDDEN, focus >= 0 || shown.event_count == 0);
    if (focus < 0) {
        return -1;
    }
    typeof(shown.events[0]) *e = &shown.events[focus];
    int64_t to = under_way ? e->end_at : e->start_at;
    int minutes = (int)((to - now + 59) / 60);
    lv_arc_set_value(ring, minutes > 60 ? 60 : minutes);
    lv_obj_set_style_arc_color(ring, lv_color_hex(e->color), LV_PART_INDICATOR);
    lv_obj_set_style_image_recolor(glow, lv_color_hex(e->color), 0);
    lv_label_set_text_fmt(ring_number, "%d", minutes);
    lv_label_set_text(ring_label, under_way ? "min left" : "min");

    char line[64], caps[64];
    snprintf(line, sizeof line, "%s · %s", under_way ? "Now" : "Next", e->calendar);
    ui_upper(caps, sizeof caps, line);
    lv_label_set_text(kicker, caps);
    lv_obj_set_style_text_color(kicker, lv_color_hex(e->color), 0);
    lv_label_set_text(event_title, e->title);
    if (under_way) {
        lv_label_set_text_fmt(event_time, "until %s", e->end);
    } else {
        lv_label_set_text_fmt(event_time, "%s to %s", e->start, e->end);
    }
    return focus;
}

static void show_chips(void)
{
    lv_obj_clean(chips);
    lv_obj_set_flag(chips, LV_OBJ_FLAG_HIDDEN, shown.all_day_count == 0);
    for (int i = 0; i < shown.all_day_count; i++) {
        lv_obj_t *chip = ui_plain(chips);
        lv_obj_set_size(chip, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
        lv_obj_set_flex_flow(chip, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(chip, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_hor(chip, 14, 0);
        lv_obj_set_style_pad_ver(chip, 6, 0);
        lv_obj_set_style_pad_column(chip, 10, 0);
        lv_obj_set_style_radius(chip, 18, 0);
        lv_obj_set_style_bg_opa(chip, 40, 0);
        lv_obj_set_style_bg_color(chip, lv_color_hex(shown.all_day[i].color), 0);
        dot(chip, 12, shown.all_day[i].color);
        lv_obj_t *label = ui_text(chip, &instrument_24, 0xf1eff7);
        lv_label_set_text(label, shown.all_day[i].title);
    }
}

static void show_ribbon(int y, int now_minute)
{
    lv_obj_clean(ribbon);
    lv_obj_set_pos(ribbon, LEFT, y);
    lv_obj_t *track = ui_plain(ribbon);
    lv_obj_set_pos(track, 0, 10);
    lv_obj_set_size(track, WIDTH, 28);
    lv_obj_set_style_radius(track, 14, 0);
    lv_obj_set_style_bg_opa(track, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(track, lv_color_hex(0x1a1922), 0);
    for (int i = 0; i < shown.event_count; i++) {
        int x1 = ribbon_x(shown.events[i].start_minute), x2 = ribbon_x(shown.events[i].end_minute);
        if (x2 - x1 < 12) {
            x2 = x1 + 12;
        }
        lv_obj_t *block = ui_plain(ribbon);
        lv_obj_set_pos(block, x1, 14);
        lv_obj_set_size(block, x2 - x1, 20);
        lv_obj_set_style_radius(block, 10, 0);
        lv_obj_set_style_bg_opa(block, shown.events[i].end_minute <= now_minute ? 70 : LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(block, lv_color_hex(shown.events[i].color), 0);
    }
    if (now_minute >= DAY_FROM && now_minute <= DAY_TO) {
        lv_obj_t *line = ui_plain(ribbon);
        lv_obj_set_pos(line, ribbon_x(now_minute) - 1, 0);
        lv_obj_set_size(line, 3, 48);
        lv_obj_set_style_radius(line, 2, 0);
        lv_obj_set_style_bg_opa(line, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(line, lv_color_white(), 0);
    }
    const char *hours[] = {"07:00", "12:00", "17:00", "23:00"};
    const int at[] = {7, 12, 17, 23};
    for (int i = 0; i < 4; i++) {
        lv_obj_t *label = ui_text(ribbon, &instrument_24, 0x7d7a8c);
        lv_label_set_text(label, hours[i]);
        lv_obj_update_layout(label);
        int x = ribbon_x(at[i] * 60) - (i == 0 ? 0 : i == 3 ? lv_obj_get_width(label) : lv_obj_get_width(label) / 2);
        lv_obj_set_pos(label, x, 54);
    }
}

/* What comes after the focus, as many as fit above the bottom edge. */
static void show_later(int y, int focus, int64_t now)
{
    lv_obj_clean(later);
    lv_obj_set_pos(later, LEFT, y);
    /* Only the room left: reaching past the bottom edge made the screen
     * scrollable, and LVGL drew a scrollbar at the right. */
    lv_obj_set_height(later, y < BOTTOM ? BOTTOM - y : 0);
    if (focus < 0) {
        return; /* the day is done */
    }
    int rows = 0;
    for (int i = focus + 1; i < shown.event_count && y + (rows + 1) * ROW <= BOTTOM; i++) {
        if (shown.events[i].end_at <= now) {
            continue;
        }
        int top = rows++ * ROW;
        lv_obj_t *at = ui_text(later, &instrument_24, 0xb4b1c2);
        lv_label_set_text(at, shown.events[i].start[0] ? shown.events[i].start : "     ");
        lv_obj_set_pos(at, 0, top);
        lv_obj_t *mark = dot(later, 12, shown.events[i].color);
        lv_obj_set_pos(mark, 88, top + 10);
        lv_obj_t *name = ui_text(later, &instrument_24, 0xf1eff7);
        lv_label_set_long_mode(name, LV_LABEL_LONG_DOT);
        lv_obj_set_width(name, WIDTH - 116);
        lv_label_set_text(name, shown.events[i].title);
        lv_obj_set_pos(name, 116, top);
    }
}

static void tick(lv_timer_t *timer)
{
    EXT_RAM_BSS_ATTR static desk_agenda_t latest;
    latest = desk_agenda();
    bool changed = latest.version != shown.version;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (tv.tv_sec < 1700000000) {
        return;
    }
    time_t local = tv.tv_sec + desk_clock().utc_offset;
    struct tm t;
    gmtime_r(&local, &t);
    int minute = t.tm_hour * 60 + t.tm_min;
    if (!changed && minute == shown_minute) {
        return;
    }
    if (changed) {
        shown = latest;
    }
    shown_minute = minute;
    if (!shown.present) {
        return;
    }

    char caps[48];
    ui_upper(caps, sizeof caps, shown.title);
    lv_label_set_text(title, caps);
    ui_upper(caps, sizeof caps, shown.count);
    lv_label_set_text(count, caps);

    int focus = show_focus(tv.tv_sec);
    int y = 96 + RING + 24;
    if (focus >= 0) {
        lv_obj_update_layout(focus_text);
        int text_bottom = lv_obj_get_y(focus_text) + lv_obj_get_height(focus_text) + 24;
        y = y > text_bottom ? y : text_bottom;
    } else {
        y = 200;
    }
    show_chips();
    if (shown.all_day_count) {
        lv_obj_set_pos(chips, LEFT, y);
        lv_obj_update_layout(chips);
        y += lv_obj_get_height(chips) + 20;
    }
    lv_obj_set_flag(ribbon, LV_OBJ_FLAG_HIDDEN, shown.event_count == 0);
    if (shown.event_count) {
        show_ribbon(y, minute);
        y += 54 + 34 + 24;
    }
    show_later(y, focus, tv.tv_sec);
}

void screen_agenda_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Light in the colour of the coming event's calendar, behind its ring. */
    glow = lv_image_create(screen);
    lv_image_set_src(glow, &glow_round);
    lv_image_set_scale(glow, 256 * 520 / 160);
    lv_obj_set_pos(glow, LEFT + RING / 2 - 80, 96 + RING / 2 - 80);
    lv_obj_set_style_image_recolor_opa(glow, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(glow, 46, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 24);
    count = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(count, 2, 0);
    lv_obj_align(count, LV_ALIGN_TOP_RIGHT, -LEFT, 24);

    ring = lv_arc_create(screen);
    lv_obj_remove_style(ring, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(ring, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_size(ring, RING, RING);
    lv_obj_set_pos(ring, LEFT, 96);
    lv_arc_set_rotation(ring, 270);
    lv_arc_set_bg_angles(ring, 0, 360);
    lv_arc_set_range(ring, 0, 60);
    lv_obj_set_style_arc_width(ring, 12, LV_PART_MAIN);
    lv_obj_set_style_arc_width(ring, 12, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(ring, lv_color_hex(0x232129), LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(ring, true, LV_PART_INDICATOR);
    ring_number = ui_text(ring, &instrument_52_bold, 0xf1eff7);
    lv_obj_align(ring_number, LV_ALIGN_CENTER, 0, -10);
    ring_label = ui_text(ring, &instrument_24, 0xb4b1c2);
    lv_obj_align(ring_label, LV_ALIGN_CENTER, 0, 30);

    /* "NEXT · WORK", the title (two lines at most) and its times, stacked. */
    focus_text = ui_plain(screen);
    lv_obj_set_pos(focus_text, TEXT_X, 108);
    lv_obj_set_size(focus_text, 720 - LEFT - TEXT_X, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(focus_text, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(focus_text, 6, 0);
    kicker = ui_text(focus_text, &instrument_24, 0x8f80ff);
    lv_obj_set_style_text_letter_space(kicker, 2, 0);
    event_title = ui_text(focus_text, &instrument_52_bold, 0xf1eff7);
    lv_label_set_long_mode(event_title, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(event_title, lv_pct(100));
    lv_obj_set_style_max_height(event_title, 2 * 62, 0);
    event_time = ui_text(focus_text, &instrument_24, 0xb4b1c2);

    /* The day is done: a calm line instead of the countdown. */
    done = ui_plain(screen);
    lv_obj_set_size(done, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(done, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(done, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(done, 16, 0);
    lv_obj_set_pos(done, LEFT, 110);
    dot(done, 16, 0x5fd39c);
    lv_obj_t *nothing = ui_text(done, &instrument_40, 0xf1eff7);
    lv_label_set_text(nothing, "Nothing more today");
    lv_obj_add_flag(done, LV_OBJ_FLAG_HIDDEN);

    chips = ui_plain(screen);
    lv_obj_set_size(chips, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(chips, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_style_pad_column(chips, 10, 0);
    lv_obj_set_style_pad_row(chips, 10, 0);

    ribbon = ui_plain(screen);
    lv_obj_set_size(ribbon, WIDTH, 90);
    later = ui_plain(screen);
    lv_obj_set_size(later, WIDTH, 0);

    lv_timer_create(tick, 1000, NULL);
}
