/* The Door panel's today view (plan.md M32, the mockups of 2026-11-04): the clock large at
 * the top left with the date under it, the temperature now and tonight's low at the top
 * right; the rain over the next two hours as a countdown over five-minute bars, or one quiet
 * line when it stays dry; then today's open reminders beside the coming week's birthdays,
 * and the wind at the bottom.
 *
 * The countdown ("Dry for 28 min, then rain until 09:25") is worded here every second from
 * the spell's times, so it runs between the hub's answers. Under the bars only the spell's
 * start and end are labelled, and "Now" and "+2 h" only where they do not touch those.
 * Bars that have passed drop off on the panel's own clock, and the weather fades with an
 * "as of" time once it is old (the hub's weather is stale, or the hub stopped answering).
 *
 * The reminders show four at a time; with more, the page turns every 8 s with a short fade
 * of the text alone (no layer) and dots by the header show which page is up. */

#include "screen_door.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "backdrops.h"
#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define WIDTH 648
#define BOX_TOP 160
#define BOX_HEIGHT 150
#define BOX_PAD 22
#define BARS_BOTTOM 108   /* in the box */
#define BAR_MAX 46
#define BAR_GAP 4
#define AXIS_TOP 114
#define LABEL_GAP 14
#define COLUMNS_WET 336
#define COLUMNS_DRY 232
#define LEFT_WIDTH 396
#define RIGHT_X 470
#define RIGHT_WIDTH 214
#define ROW_HEIGHT 56
#define BIRTHDAY_HEIGHT 70
#define DAY_GAP 12        /* between a birthday's day and the name */
#define TOP_MM 3.0f
#define WET_MM 0.1f       /* as the hub's desk_clock.WET_MM */
#define ROWS 4            /* reminders a page: always room for the wind line */
#define PAGES ((DESK_DOOR_REMINDERS + ROWS - 1) / ROWS)
#define PAGE_MS 8000
#define FADE_MS 220
#define DOT 8
#define STALE_AFTER (20 * 60) /* the hub reads the weather every 5 minutes */

#define GREY 0x8a8794
#define FAINT 0x6c6a78
#define RAIN_BLUE 0x5aa9ff
#define RAIN_LIGHT 0x9cc8ff
#define VIOLET 0x9d8cff
#define ROSE 0xf2b3cf

enum { AXIS_NOW, AXIS_FROM, AXIS_UNTIL, AXIS_END, AXES };

static lv_obj_t *clock_label, *date, *temperature, *weather, *dry_line, *box, *lead, *rest;
static lv_obj_t *bars[DESK_DOOR_RAIN], *axis[AXES];
static lv_obj_t *columns, *reminders_title, *reminder_rows[ROWS], *reminder_bar[ROWS];
static lv_obj_t *reminder_at[ROWS], *reminder_text[ROWS], *dots[PAGES];
static lv_obj_t *more, *no_reminders, *birthdays_title, *birthday_name[DESK_DOOR_BIRTHDAYS];
static lv_obj_t *birthday_when[DESK_DOOR_BIRTHDAYS], *birthday_day[DESK_DOOR_BIRTHDAYS];
static lv_obj_t *no_birthdays, *wind;
EXT_RAM_BSS_ATTR static desk_door_t shown; /* off the LVGL task's small stack */
static int page;     /* the reminders' page on screen */
static int passed;   /* rain bars that have passed since the hub's answer */
static bool faded;   /* the weather is old */

static void clock_of(int64_t at, int offset, char *to, size_t size)
{
    time_t local = (time_t)(at + offset);
    struct tm t;
    gmtime_r(&local, &t);
    snprintf(to, size, "%02d:%02d", t.tm_hour, t.tm_min);
}

static void minutes_of(int64_t seconds, char *to, size_t size)
{
    int minutes = (int)((seconds + 59) / 60);
    if (minutes < 60) {
        snprintf(to, size, "%d min", minutes);
    } else if (minutes % 60 == 0) {
        snprintf(to, size, "%d h", minutes / 60);
    } else {
        snprintf(to, size, "%d h %d min", minutes / 60, minutes % 60);
    }
}

/* The bars still to come and when the first of them starts. */
static int bars_left(void)
{
    return shown.rain_count - passed;
}

static int64_t bars_from(void)
{
    return shown.rain_from + (int64_t)passed * shown.rain_step;
}

/* How many of the hub's bars lie wholly in the past by the panel's clock. */
static int bars_passed(int64_t now)
{
    if (shown.rain_from <= 0 || shown.rain_step <= 0 || now <= shown.rain_from) {
        return 0;
    }
    int64_t gone = (now - shown.rain_from) / shown.rain_step;
    return gone > shown.rain_count ? shown.rain_count : (int)gone;
}

/* Where along the bars a time falls, in the box's pixels. */
static int32_t x_of(int64_t at)
{
    int64_t span = (int64_t)bars_left() * shown.rain_step;
    if (span <= 0) {
        return BOX_PAD;
    }
    int64_t into = at - bars_from();
    into = into < 0 ? 0 : into > span ? span : into;
    return BOX_PAD + (int32_t)(into * (WIDTH - 2 * BOX_PAD) / span);
}

/* The labels under the bars: the spell's edges first, then the ends where they fit. */
static void place_axis(int offset)
{
    char text[12];
    int32_t left[AXES], right[AXES];
    bool placed[AXES] = {false};
    int64_t at[AXES] = {[AXIS_FROM] = shown.wet_from, [AXIS_UNTIL] = shown.wet_until};
    static const int order[AXES] = {AXIS_FROM, AXIS_UNTIL, AXIS_NOW, AXIS_END};
    for (int k = 0; k < AXES; k++) {
        int which = order[k];
        lv_obj_add_flag(axis[which], LV_OBJ_FLAG_HIDDEN);
        if ((which == AXIS_FROM || which == AXIS_UNTIL) && at[which] == 0) {
            continue;
        }
        if (which == AXIS_NOW) {
            snprintf(text, sizeof text, "Now");
        } else if (which == AXIS_END && passed == 0) {
            snprintf(text, sizeof text, "+2 h");
        } else if (which == AXIS_END) { /* the hub's answer is old: where the bars end */
            clock_of(bars_from() + (int64_t)bars_left() * shown.rain_step, offset, text, sizeof text);
        } else {
            clock_of(at[which], offset, text, sizeof text);
        }
        lv_label_set_text(axis[which], text);
        int32_t width = lv_text_get_width(text, strlen(text), &instrument_24, 0);
        int32_t x = which == AXIS_NOW ? BOX_PAD
                    : which == AXIS_END ? WIDTH - BOX_PAD - width
                                        : x_of(at[which]) - width / 2;
        x = LV_CLAMP(BOX_PAD, x, WIDTH - BOX_PAD - width);
        bool clash = false;
        for (int other = 0; other < AXES; other++) {
            if (placed[other] && x < right[other] + LABEL_GAP && x + width + LABEL_GAP > left[other]) {
                clash = true;
            }
        }
        if (clash) {
            continue;
        }
        left[which] = x;
        right[which] = x + width;
        placed[which] = true;
        lv_obj_set_pos(axis[which], x, AXIS_TOP);
        lv_obj_remove_flag(axis[which], LV_OBJ_FLAG_HIDDEN);
    }
}

/* The countdown, worded on the panel's own clock. */
static void word_rain(int64_t now, int offset)
{
    char first[48], second[48], when[24];
    bool spell_over = shown.wet_until != 0 && shown.wet_until <= now;
    bool wet = shown.wet && !spell_over && bars_left() > 0;
    lv_obj_set_flag(box, LV_OBJ_FLAG_HIDDEN, !wet);
    lv_obj_set_flag(dry_line, LV_OBJ_FLAG_HIDDEN, wet);
    lv_obj_set_y(columns, wet ? COLUMNS_WET : COLUMNS_DRY);
    if (!wet) {
        lv_label_set_text(dry_line, bars_left() <= 0  ? "No rain forecast"
                                    : passed == 0     ? "Dry for the next 2 hours"
                                                      : "Dry for now");
        return;
    }
    if (shown.wet_from == 0 || shown.wet_from <= now) {
        snprintf(first, sizeof first, "Rain now");
        if (shown.wet_until) {
            clock_of(shown.wet_until, offset, when, sizeof when);
            snprintf(second, sizeof second, "dry at %s", when);
        } else {
            snprintf(second, sizeof second, passed == 0 ? "for the next 2 hours" : "for now");
        }
    } else {
        minutes_of(shown.wet_from - now, when, sizeof when);
        snprintf(first, sizeof first, "Dry for %s", when);
        if (shown.wet_until) {
            clock_of(shown.wet_until, offset, when, sizeof when);
            snprintf(second, sizeof second, "then rain until %s", when);
        } else {
            snprintf(second, sizeof second, "then rain");
        }
    }
    lv_label_set_text(lead, first);
    lv_label_set_text(rest, second);
}

/* The bars still to come across the box's width: as the hub's answer ages, the passed
 * ones drop off the left and the rest spread out. */
static void draw_bars(void)
{
    int count = bars_left();
    int32_t step = count > 0 ? (WIDTH - 2 * BOX_PAD) / count : 0;
    for (int i = 0; i < DESK_DOOR_RAIN; i++) {
        if (i >= count) {
            lv_obj_add_flag(bars[i], LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        float mm = shown.rain[passed + i];
        bool wet = mm >= WET_MM;
        float share = mm >= TOP_MM ? 1.0f : mm / TOP_MM;
        int32_t height = wet ? 8 + (int32_t)(share * (BAR_MAX - 8)) : 3;
        uint32_t colour = !wet ? 0x2b3a55 : faded ? 0x4a4f5c : share > 0.5f ? RAIN_LIGHT : RAIN_BLUE;
        lv_obj_set_size(bars[i], step - BAR_GAP, height);
        lv_obj_set_pos(bars[i], BOX_PAD + i * step, BARS_BOTTOM - height);
        lv_obj_set_style_bg_color(bars[i], lv_color_hex(colour), 0);
        lv_obj_remove_flag(bars[i], LV_OBJ_FLAG_HIDDEN);
    }
}

/* The weather's colours, faded to greys while it is old, and the bottom line. */
static void colour_weather(int offset)
{
    lv_obj_set_style_text_color(temperature, lv_color_hex(faded ? GREY : 0xffffff), 0);
    lv_obj_set_style_text_color(weather, lv_color_hex(faded ? FAINT : GREY), 0);
    lv_obj_set_style_text_color(dry_line, lv_color_hex(faded ? GREY : 0xa6adc8), 0);
    lv_obj_set_style_text_color(lead, lv_color_hex(faded ? GREY : 0xcfe3ff), 0);
    lv_obj_set_style_text_color(rest, lv_color_hex(faded ? FAINT : 0x9fb0c8), 0);
    lv_obj_set_style_border_color(box, lv_color_hex(faded ? 0x2a2a33 : 0x24405f), 0);
    for (int i = AXIS_FROM; i <= AXIS_UNTIL; i++) {
        lv_obj_set_style_text_color(axis[i], lv_color_hex(faded ? FAINT : RAIN_LIGHT), 0);
    }
    char when[12];
    if (!faded) {
        lv_label_set_text(wind, shown.wind);
    } else if (shown.weather_at == 0) {
        lv_label_set_text(wind, "No weather from the hub");
    } else {
        clock_of(shown.weather_at, offset, when, sizeof when);
        if (shown.wind[0]) {
            lv_label_set_text_fmt(wind, "%s · weather as of %s", shown.wind, when);
        } else {
            lv_label_set_text_fmt(wind, "Weather as of %s", when);
        }
    }
}

/* One page of the reminders, and the dots that say which. */
static void show_page(void)
{
    int pages = (shown.reminder_count + ROWS - 1) / ROWS;
    if (page >= pages) {
        page = 0;
    }
    int first = page * ROWS, on_page = 0;
    for (int i = 0; i < ROWS; i++) {
        int at = first + i;
        bool on = at < shown.reminder_count;
        lv_obj_set_flag(reminder_rows[i], LV_OBJ_FLAG_HIDDEN, !on);
        if (!on) {
            continue;
        }
        on_page++;
        bool timed = shown.reminders[at].at[0] != '\0';
        lv_label_set_text(reminder_at[i], timed ? shown.reminders[at].at : "");
        lv_obj_set_flag(reminder_at[i], LV_OBJ_FLAG_HIDDEN, !timed);
        lv_label_set_text(reminder_text[i], shown.reminders[at].title);
        lv_obj_set_x(reminder_text[i], timed ? 100 : 20);
        lv_obj_set_width(reminder_text[i], LEFT_WIDTH - (timed ? 100 : 20));
    }
    lv_obj_set_flag(no_reminders, LV_OBJ_FLAG_HIDDEN, shown.reminder_count > 0);
    /* Past the twelve the hub sends: a line under the last page. */
    bool last = page == pages - 1;
    lv_obj_set_flag(more, LV_OBJ_FLAG_HIDDEN, shown.more_reminders == 0 || !last);
    lv_label_set_text_fmt(more, "and %d more", shown.more_reminders);
    lv_obj_set_y(more, 42 + on_page * ROW_HEIGHT);
    for (int i = 0; i < PAGES; i++) {
        lv_obj_set_flag(dots[i], LV_OBJ_FLAG_HIDDEN, pages < 2 || i >= pages);
        lv_obj_set_style_bg_opa(dots[i], i == page ? LV_OPA_COVER : 70, 0);
    }
}

/* The fade sets the text's and the bar's own opacity, so no layer is drawn. */
static void set_rows_opa(void *unused, int32_t opa)
{
    (void)unused;
    for (int i = 0; i < ROWS; i++) {
        lv_obj_set_style_text_opa(reminder_at[i], opa, 0);
        lv_obj_set_style_text_opa(reminder_text[i], opa, 0);
        lv_obj_set_style_bg_opa(reminder_bar[i], opa, 0);
    }
    lv_obj_set_style_text_opa(more, opa, 0);
}

static void fade(int32_t from, int32_t to, lv_anim_completed_cb_t done)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, reminder_rows); /* any key: one fade at a time */
    lv_anim_set_exec_cb(&anim, (lv_anim_exec_xcb_t)set_rows_opa);
    lv_anim_set_values(&anim, from, to);
    lv_anim_set_duration(&anim, FADE_MS);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_set_completed_cb(&anim, done);
    lv_anim_start(&anim);
}

static void faded_out(lv_anim_t *anim)
{
    (void)anim;
    page++;
    show_page();
    fade(LV_OPA_TRANSP, LV_OPA_COVER, NULL);
}

static void turn_page(lv_timer_t *timer)
{
    (void)timer;
    if (shown.present && shown.reminder_count > ROWS) {
        fade(LV_OPA_COVER, LV_OPA_TRANSP, faded_out);
    }
}

static void fill(void)
{
    char text[96];
    lv_label_set_text(date, shown.date);
    if (shown.has_temperature) {
        lv_label_set_text_fmt(temperature, "%d°", shown.temperature);
    } else {
        lv_label_set_text(temperature, "");
    }
    if (shown.description[0] && shown.tonight[0]) {
        snprintf(text, sizeof text, "%s · %s", shown.description, shown.tonight);
    } else {
        snprintf(text, sizeof text, "%s", shown.description[0] ? shown.description : shown.tonight);
    }
    lv_label_set_text(weather, text);
    show_page();

    /* The day column is as wide as its widest day ("Mon", or "Today"), so the names keep
     * the rest; "turns 22" goes under the name, so the age can't be read as the date. */
    int32_t day_width = 0;
    for (int i = 0; i < shown.birthday_count; i++) {
        const char *day = shown.birthdays[i].when;
        int32_t width = lv_text_get_width(day, strlen(day), &instrument_24, 0);
        day_width = width > day_width ? width : day_width;
    }
    int32_t name_x = RIGHT_X - LEFT + day_width + DAY_GAP;
    int32_t name_width = RIGHT_WIDTH - day_width - DAY_GAP;
    for (int i = 0; i < DESK_DOOR_BIRTHDAYS; i++) {
        bool on = i < shown.birthday_count;
        lv_obj_set_flag(birthday_day[i], LV_OBJ_FLAG_HIDDEN, !on);
        lv_obj_set_flag(birthday_name[i], LV_OBJ_FLAG_HIDDEN, !on);
        lv_obj_set_flag(birthday_when[i], LV_OBJ_FLAG_HIDDEN, !on || shown.birthdays[i].turns <= 0);
        if (!on) {
            continue;
        }
        uint32_t accent = shown.birthdays[i].today ? ROSE : VIOLET;
        lv_label_set_text(birthday_day[i], shown.birthdays[i].when);
        lv_obj_set_style_text_color(birthday_day[i], lv_color_hex(accent), 0);
        lv_label_set_text(birthday_name[i], shown.birthdays[i].name);
        lv_obj_set_style_text_color(birthday_name[i], lv_color_hex(shown.birthdays[i].today ? ROSE : 0xf2f1f6), 0);
        lv_obj_set_x(birthday_name[i], name_x);
        lv_obj_set_width(birthday_name[i], name_width);
        lv_label_set_text_fmt(birthday_when[i], "turns %d", shown.birthdays[i].turns);
        lv_obj_set_style_text_color(birthday_when[i], lv_color_hex(shown.birthdays[i].today ? ROSE : GREY), 0);
        lv_obj_set_x(birthday_when[i], name_x);
        lv_obj_set_width(birthday_when[i], name_width);
    }
    lv_obj_set_flag(no_birthdays, LV_OBJ_FLAG_HIDDEN, shown.birthday_count > 0);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    static int64_t worded = -1;
    if (desk_door_version() != version) {
        desk_door_copy(&shown);
        version = shown.version;
        worded = -1;
        if (shown.present) {
            fill();
        }
    }
    struct timeval tv;
    gettimeofday(&tv, NULL);
    int offset = desk_clock().utc_offset;
    time_t local = tv.tv_sec + offset;
    struct tm t;
    gmtime_r(&local, &t);
    lv_label_set_text_fmt(clock_label, "%02d:%02d", t.tm_hour, t.tm_min);
    if (shown.present && tv.tv_sec / 60 != worded) { /* the words change by the minute */
        bool fresh = worded == -1;
        worded = tv.tv_sec / 60;
        int now_passed = bars_passed(tv.tv_sec);
        bool now_faded = shown.stale || shown.weather_at == 0 ||
                         tv.tv_sec - shown.weather_at > STALE_AFTER;
        bool redraw = fresh || now_passed != passed || now_faded != faded;
        passed = now_passed;
        faded = now_faded;
        if (redraw) {
            draw_bars();
            colour_weather(offset);
        }
        word_rain(tv.tv_sec, offset);
        place_axis(offset);
    }
}

static lv_obj_t *header(lv_obj_t *parent, const char *text)
{
    lv_obj_t *label = ui_text(parent, &instrument_24, GREY);
    lv_obj_set_style_text_letter_space(label, 2, 0);
    lv_label_set_text(label, text);
    return label;
}

void screen_door_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    clock_label = ui_text(screen, &instrument_time, 0xffffff);
    lv_label_set_text(clock_label, "--:--");
    lv_obj_set_pos(clock_label, LEFT - 4, 18);
    date = ui_one_line(screen, &instrument_24, GREY, 400);
    lv_obj_set_pos(date, LEFT, 112);
    temperature = ui_text(screen, &instrument_52_bold, 0xffffff);
    lv_obj_align(temperature, LV_ALIGN_TOP_RIGHT, -LEFT, 28);
    weather = ui_text(screen, &instrument_24, GREY);
    lv_obj_align(weather, LV_ALIGN_TOP_RIGHT, -LEFT, 92);

    dry_line = ui_text(screen, &instrument_28_bold, 0xa6adc8);
    lv_obj_set_pos(dry_line, LEFT, 172);

    box = ui_plain(screen);
    lv_obj_set_size(box, WIDTH, BOX_HEIGHT);
    lv_obj_set_pos(box, LEFT, BOX_TOP);
    lv_obj_set_style_radius(box, 18, 0);
    lv_obj_set_style_bg_color(box, lv_color_hex(0x0b1220), 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(box, lv_color_hex(0x24405f), 0);
    lv_obj_set_style_border_width(box, 1, 0);
    backdrops_glass(box);
    lead = ui_text(box, &instrument_28_bold, 0xcfe3ff);
    lv_obj_set_pos(lead, BOX_PAD, 16);
    rest = ui_text(box, &instrument_24, 0x9fb0c8);
    lv_obj_align(rest, LV_ALIGN_TOP_RIGHT, -BOX_PAD, 20);
    for (int i = 0; i < DESK_DOOR_RAIN; i++) {
        bars[i] = ui_plain(box);
        lv_obj_set_style_bg_opa(bars[i], LV_OPA_COVER, 0);
        lv_obj_set_style_radius(bars[i], 2, 0);
        lv_obj_add_flag(bars[i], LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < AXES; i++) {
        axis[i] = ui_text(box, &instrument_24, i == AXIS_NOW || i == AXIS_END ? FAINT : RAIN_LIGHT);
        lv_obj_add_flag(axis[i], LV_OBJ_FLAG_HIDDEN);
    }

    columns = ui_plain(screen);
    lv_obj_set_size(columns, WIDTH, 720 - COLUMNS_DRY - 60);
    lv_obj_set_pos(columns, LEFT, COLUMNS_WET);
    reminders_title = header(columns, "TODAY");
    lv_obj_set_pos(reminders_title, 0, 0);
    lv_obj_update_layout(reminders_title);
    int32_t dots_x = lv_obj_get_width(reminders_title) + 16;
    for (int i = 0; i < PAGES; i++) {
        dots[i] = ui_plain(columns);
        lv_obj_set_size(dots[i], DOT, DOT);
        lv_obj_set_pos(dots[i], dots_x + i * 2 * DOT, 10);
        lv_obj_set_style_radius(dots[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(dots[i], lv_color_hex(VIOLET), 0);
        lv_obj_add_flag(dots[i], LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < ROWS; i++) {
        reminder_rows[i] = ui_plain(columns);
        lv_obj_set_size(reminder_rows[i], LEFT_WIDTH, ROW_HEIGHT - 8);
        lv_obj_set_pos(reminder_rows[i], 0, 40 + i * ROW_HEIGHT);
        lv_obj_add_flag(reminder_rows[i], LV_OBJ_FLAG_HIDDEN);
        lv_obj_t *bar = reminder_bar[i] = ui_plain(reminder_rows[i]);
        lv_obj_set_size(bar, 4, 34);
        lv_obj_align(bar, LV_ALIGN_LEFT_MID, 0, 0);
        lv_obj_set_style_bg_color(bar, lv_color_hex(VIOLET), 0);
        lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
        reminder_at[i] = ui_text(reminder_rows[i], &instrument_24, VIOLET);
        lv_obj_align(reminder_at[i], LV_ALIGN_LEFT_MID, 20, 0);
        reminder_text[i] = ui_one_line(reminder_rows[i], &instrument_28_bold, 0xf2f1f6, LEFT_WIDTH - 100);
        lv_obj_align(reminder_text[i], LV_ALIGN_LEFT_MID, 100, 0);
    }
    more = ui_text(columns, &instrument_24, FAINT);
    lv_obj_set_x(more, 20);
    lv_obj_add_flag(more, LV_OBJ_FLAG_HIDDEN);
    no_reminders = ui_text(columns, &instrument_24, FAINT);
    lv_label_set_text(no_reminders, "Nothing to remember");
    lv_obj_set_pos(no_reminders, 0, 48);

    birthdays_title = header(columns, "BIRTHDAYS");
    lv_obj_set_pos(birthdays_title, RIGHT_X - LEFT, 0);
    for (int i = 0; i < DESK_DOOR_BIRTHDAYS; i++) {
        birthday_day[i] = ui_text(columns, &instrument_24, VIOLET);
        lv_obj_set_pos(birthday_day[i], RIGHT_X - LEFT, 48 + i * BIRTHDAY_HEIGHT); /* on the name's line */
        lv_obj_add_flag(birthday_day[i], LV_OBJ_FLAG_HIDDEN);
        birthday_name[i] = ui_one_line(columns, &instrument_28_bold, 0xf2f1f6, RIGHT_WIDTH);
        lv_obj_set_pos(birthday_name[i], RIGHT_X - LEFT, 44 + i * BIRTHDAY_HEIGHT);
        birthday_when[i] = ui_one_line(columns, &instrument_24, GREY, RIGHT_WIDTH);
        lv_obj_set_pos(birthday_when[i], RIGHT_X - LEFT, 76 + i * BIRTHDAY_HEIGHT);
        lv_obj_add_flag(birthday_name[i], LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(birthday_when[i], LV_OBJ_FLAG_HIDDEN);
    }
    no_birthdays = ui_text(columns, &instrument_24, FAINT);
    lv_label_set_text(no_birthdays, "None this week");
    lv_obj_set_pos(no_birthdays, RIGHT_X - LEFT, 48);

    wind = ui_text(screen, &instrument_24, FAINT);
    lv_obj_set_pos(wind, LEFT, 672);

    lv_timer_create(tick, 1000, NULL);
    lv_timer_create(turn_page, PAGE_MS, NULL);
    tick(NULL);
}
