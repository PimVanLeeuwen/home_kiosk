/* A piece (plan.md M27, step 4): the hub paints the picture (the background, backdrops.c)
 * and places the words; this lays them out, and keeps the time where the piece asks for it
 * by the panel's own clock. One instance per piece, the same code for all of them.
 *
 * The orbit clock (C) adds its bodies: the hour, the minute and the second going round the
 * hub's painted sun on its orbits, the second with a fading tail, ten steps a second while
 * it shows; small objects moved by their real position, nothing transformed. */

#include "screen_piece.h"

#include <math.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>

#include "desk.h"
#include "desk_piece.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_24);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_clock);
LV_FONT_DECLARE(instrument_time);

#define ORBIT_X 360   /* the sun, and the orbits' radii, as app/paint_orbit.py paints them */
#define ORBIT_Y 360
#define TAIL 5
#define ORBIT_MS 100
static const int RADII[3] = {118, 196, 276};

typedef struct {
    int which;
    lv_obj_t *bodies[3], *tail[TAIL];
    uint32_t version;
    int minute;
    lv_obj_t *labels[PIECE_LABELS], *clock;
    desk_piece_t shown;
} piece_screen_t;

static const lv_font_t *font_of(int font)
{
    switch (font) {
    case 1:
        return &instrument_28_bold;
    case 2:
        return &instrument_40;
    case 3:
        return &instrument_52_bold;
    case 4:
        return &instrument_clock;
    case 5:
        return &instrument_time;
    default:
        return &instrument_24;
    }
}

static void place(lv_obj_t *label, const piece_label_t *l, const char *text)
{
    const lv_font_t *font = font_of(l->font);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(l->colour), 0);
    lv_obj_set_style_text_letter_space(label, l->spacing, 0);
    lv_obj_set_style_text_align(label, l->align == PIECE_CENTRE   ? LV_TEXT_ALIGN_CENTER
                                       : l->align == PIECE_RIGHT ? LV_TEXT_ALIGN_RIGHT
                                                                 : LV_TEXT_ALIGN_LEFT,
                                0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_obj_set_size(label, l->width, (l->lines ? l->lines : 1) * lv_font_get_line_height(font));
    int x = l->align == PIECE_CENTRE ? l->x - l->width / 2 : l->align == PIECE_RIGHT ? l->x - l->width : l->x;
    lv_obj_set_pos(label, x, l->y);
    lv_label_set_text(label, text);
    lv_obj_remove_flag(label, LV_OBJ_FLAG_HIDDEN);
}

static void tick(lv_timer_t *timer)
{
    piece_screen_t *p = lv_timer_get_user_data(timer);
    if (desk_piece_version(p->which) != p->version) {
        desk_piece_copy(p->which, &p->shown);
        p->version = p->shown.version;
        for (int i = 0; i < PIECE_LABELS; i++) {
            if (i < p->shown.label_count) {
                place(p->labels[i], &p->shown.labels[i], p->shown.labels[i].text);
            } else {
                lv_obj_add_flag(p->labels[i], LV_OBJ_FLAG_HIDDEN);
            }
        }
        lv_obj_set_flag(p->clock, LV_OBJ_FLAG_HIDDEN, !p->shown.has_clock);
        p->minute = -1;
    }
    if (!p->shown.has_clock) {
        return;
    }
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (tv.tv_sec < 1700000000) {
        return; /* until the hub has set the clock */
    }
    time_t local = tv.tv_sec + desk_clock().utc_offset;
    struct tm t;
    gmtime_r(&local, &t);
    if (t.tm_min != p->minute) {
        p->minute = t.tm_min;
        char time_text[8];
        snprintf(time_text, sizeof time_text, "%02d:%02d", t.tm_hour, t.tm_min);
        place(p->clock, &p->shown.clock, time_text);
    }
}

static lv_obj_t *body(lv_obj_t *screen, int size, uint32_t colour, lv_opa_t glow)
{
    lv_obj_t *b = ui_plain(screen);
    lv_obj_set_size(b, size, size);
    lv_obj_set_style_radius(b, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(b, lv_color_hex(colour), 0);
    lv_obj_set_style_bg_opa(b, LV_OPA_COVER, 0);
    lv_obj_set_style_shadow_width(b, size, 0);
    lv_obj_set_style_shadow_color(b, lv_color_hex(colour), 0);
    lv_obj_set_style_shadow_opa(b, glow, 0);
    return b;
}

static void at_angle(lv_obj_t *b, int radius, float turn) /* turn: 0 to 1 from the top, clockwise */
{
    float a = turn * 2 * (float)M_PI - (float)M_PI / 2;
    int size = lv_obj_get_width(b);
    lv_obj_set_pos(b, ORBIT_X + (int)(radius * cosf(a)) - size / 2, ORBIT_Y + (int)(radius * sinf(a)) - size / 2);
}

static void orbit(lv_timer_t *timer)
{
    piece_screen_t *p = lv_timer_get_user_data(timer);
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (lv_screen_active() != lv_obj_get_screen(p->bodies[0]) || tv.tv_sec < 1700000000) {
        return;
    }
    time_t local = tv.tv_sec + desk_clock().utc_offset;
    struct tm t;
    gmtime_r(&local, &t);
    float second = (t.tm_sec + tv.tv_usec / 1e6f) / 60, minute = (t.tm_min + second) / 60;
    float hour = (t.tm_hour % 12 + minute) / 12;
    at_angle(p->bodies[0], RADII[0], hour);
    at_angle(p->bodies[1], RADII[1], minute);
    at_angle(p->bodies[2], RADII[2], second);
    for (int i = 0; i < TAIL; i++) {
        at_angle(p->tail[i], RADII[2], second - (i + 1) * 0.006f);
    }
}

void screen_piece_create(lv_obj_t *screen, int which)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
    piece_screen_t *p = heap_caps_calloc(1, sizeof *p, MALLOC_CAP_SPIRAM);
    p->which = which;
    p->minute = -1;
    for (int i = 0; i < PIECE_LABELS; i++) {
        p->labels[i] = ui_text(screen, &instrument_24, 0xffffff);
        lv_obj_add_flag(p->labels[i], LV_OBJ_FLAG_HIDDEN);
    }
    p->clock = ui_text(screen, &instrument_clock, 0xffffff);
    lv_obj_add_flag(p->clock, LV_OBJ_FLAG_HIDDEN);
    lv_timer_t *timer = lv_timer_create(tick, 1000, p);
    tick(timer);
    if (which == PIECE_ORBIT) {
        for (int i = 0; i < TAIL; i++) {
            p->tail[i] = body(screen, 8 - i, 0xe2dcff, 0);
            lv_obj_set_style_bg_opa(p->tail[i], (lv_opa_t)(150 - i * 28), 0);
        }
        p->bodies[0] = body(screen, 30, 0xffb86b, 140);
        p->bodies[1] = body(screen, 20, 0xc3b9ff, 120);
        p->bodies[2] = body(screen, 11, 0xffffff, 160);
        lv_timer_create(orbit, ORBIT_MS, p);
    }
}
