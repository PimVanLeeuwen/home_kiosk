/* A piece (plan.md M27, step 4): the hub paints the picture (the background, backdrops.c)
 * and places the words; this lays them out, and keeps the time where the piece asks for it
 * by the panel's own clock. One instance per piece, the same code for all of them.
 *
 * The orbit clock (C) adds its bodies: the hour, the minute and the second going round the
 * hub's painted sun on its orbits, the second with a fading tail, 25 steps a second while
 * it shows (at ten it jumped about 3 px a step on the outer orbit); small objects moved by
 * their real position, nothing transformed. The hour and the minute, which move less than a
 * pixel a second, are placed once a second.
 *
 * The countdown (K) sends sparks streaming out of the hub's painted tunnel: from its core,
 * the day, towards you, faster and bigger as they come, 25 steps a second.
 *
 * The last run (plan.md M28, A), and your streets (D) on a run day, have a light running the
 * route, from the hub's `path`: a lap of six seconds with a short tail, then a breath, 25 steps
 * a second. */

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
#define ORBIT_MS 40
static const int RADII[3] = {118, 196, 276};

#define CORE_X 360    /* the tunnel's core, as app/paint_countdown.py paints it */
#define CORE_Y 200
#define SPARKS 13     /* each moves two areas a step: under LVGL's 32 */
#define SPARK_MS 40
#define SPARK_REACH 440

typedef struct {
    lv_obj_t *dot;
    float angle, t, speed;
} spark_t;

#define RUN_TAIL 5
#define RUN_STEP_MS 40
#define RUN_LAP_MS 6000
#define RUN_PAUSE 0.25f /* a quarter of a lap at rest between laps */
#define RUN_TAIL_GAP 0.012f

typedef struct {
    int which;
    lv_obj_t *bodies[3], *tail[TAIL];
    uint32_t version;
    int minute;
    int orbit_second; /* the second the hour and the minute were last placed in */
    lv_obj_t *labels[PIECE_LABELS], *clock;
    spark_t sparks[SPARKS];
    lv_obj_t *runner[RUN_TAIL + 1]; /* the light first, then its tail */
    float lap;
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
    if (t.tm_sec != p->orbit_second) {
        p->orbit_second = t.tm_sec;
        at_angle(p->bodies[0], RADII[0], hour);
        at_angle(p->bodies[1], RADII[1], minute);
    }
    at_angle(p->bodies[2], RADII[2], second);
    for (int i = 0; i < TAIL; i++) {
        at_angle(p->tail[i], RADII[2], second - (i + 1) * 0.006f);
    }
}

static float chance(void) /* 0 to 1: a small generator of its own */
{
    static uint32_t seed = 2463534242u;
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return (seed & 0xffffff) / (float)0x1000000;
}

static void spark_start(spark_t *s, float t)
{
    s->angle = chance() * 2 * (float)M_PI;
    s->speed = 0.006f + chance() * 0.008f;
    s->t = t;
}

static void sparks(lv_timer_t *timer)
{
    piece_screen_t *p = lv_timer_get_user_data(timer);
    if (lv_screen_active() != lv_obj_get_screen(p->sparks[0].dot)) {
        return;
    }
    for (int i = 0; i < SPARKS; i++) {
        spark_t *s = &p->sparks[i];
        s->t += s->speed;
        if (s->t >= 1) {
            spark_start(s, 0);
        }
        /* Perspective: slow by the core, rushing past near you; the tunnel bends down. */
        float r = s->t * s->t * SPARK_REACH;
        int size = 2 + (int)(s->t * 5);
        int x = CORE_X + (int)(r * cosf(s->angle));
        int y = CORE_Y + (int)(r * sinf(s->angle) * 0.86f + s->t * s->t * 70);
        lv_obj_set_size(s->dot, size, size);
        lv_obj_set_pos(s->dot, x - size / 2, y - size / 2);
        float fade = s->t < 0.15f ? s->t / 0.15f : s->t > 0.7f ? (1 - s->t) / 0.3f : 1;
        lv_obj_set_style_bg_opa(s->dot, (lv_opa_t)(230 * fade), 0);
    }
}

/* The point `share` (0 to 1) of the way along the path, between its points. */
static void along(const desk_piece_t *piece, float share, int *x, int *y)
{
    float at = share * (piece->path_count - 1);
    int i = (int)at;
    if (i >= piece->path_count - 1) {
        i = piece->path_count - 2;
    }
    float f = at - i;
    *x = (int)(piece->path[i][0] + f * (piece->path[i + 1][0] - piece->path[i][0]));
    *y = (int)(piece->path[i][1] + f * (piece->path[i + 1][1] - piece->path[i][1]));
}

static void run_light(lv_timer_t *timer)
{
    piece_screen_t *p = lv_timer_get_user_data(timer);
    if (lv_screen_active() != lv_obj_get_screen(p->runner[0])) {
        return;
    }
    bool route = p->shown.path_count >= 2;
    p->lap += (float)RUN_STEP_MS / RUN_LAP_MS;
    if (p->lap > 1 + RUN_PAUSE) {
        p->lap = 0;
    }
    for (int k = 0; k <= RUN_TAIL; k++) {
        float share = p->lap - k * RUN_TAIL_GAP;
        bool on = route && share >= 0 && share <= 1;
        lv_obj_set_flag(p->runner[k], LV_OBJ_FLAG_HIDDEN, !on);
        if (on) {
            int x, y, size = lv_obj_get_width(p->runner[k]);
            along(&p->shown, share, &x, &y);
            lv_obj_set_pos(p->runner[k], x - size / 2, y - size / 2);
        }
    }
}

void screen_piece_create(lv_obj_t *screen, int which)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);
    piece_screen_t *p = heap_caps_calloc(1, sizeof *p, MALLOC_CAP_SPIRAM);
    p->which = which;
    p->minute = -1;
    p->orbit_second = -1;
    if (which == PIECE_COUNTDOWN) { /* first, so the sparks pass under the words */
        for (int i = 0; i < SPARKS; i++) {
            p->sparks[i].dot = body(screen, 3, 0xfff1dc, 0);
            spark_start(&p->sparks[i], (float)i / SPARKS);
        }
        lv_timer_create(sparks, SPARK_MS, p);
    }
    if (which == PIECE_RUN || which == PIECE_STREETS) { /* under the words, as the sparks */
        for (int k = RUN_TAIL; k >= 0; k--) {
            p->runner[k] = k ? body(screen, 9 - k, 0xffd2a0, 0) : body(screen, 14, 0xfff4de, 200);
            if (k) {
                lv_obj_set_style_bg_opa(p->runner[k], (lv_opa_t)(220 - k * 36), 0);
            }
            lv_obj_add_flag(p->runner[k], LV_OBJ_FLAG_HIDDEN);
        }
        lv_timer_create(run_light, RUN_STEP_MS, p);
    }
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
