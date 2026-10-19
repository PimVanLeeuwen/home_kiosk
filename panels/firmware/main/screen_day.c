/* The Now panel's day view (plan.md M20): the sun's arc over a sky band from
 * night through dawn, day and dusk, the temperature from 06:00 to midnight as a
 * curve, the chance of rain per hour, and a sentence on the day. As in the
 * desk-panels mockup's forecast screen. Values come ready-made from the hub
 * (app/desk.py); the now line follows the panel's own clock.
 *
 * The chart is drawn once into a canvas when the hub's answer changes: drawn
 * from a draw event, LVGL repeats every shape for every strip of every frame,
 * which held the display lock for seconds. Sun, moon and the now line sit on
 * top as objects. */

#include "screen_day.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "desk.h"
#include "lvgl.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_round);

/* The chart: hours 6 to 24 across, in four bands from the top. */
#define LEFT 36
#define WIDTH 648
#define SKY_TOP 236
#define HORIZON 360    /* the sky band's bottom and the sun's horizon */
#define ARC 100        /* the sun's arc at noon above the horizon */
#define CURVE_TOP 392
#define CURVE_BOTTOM 498
#define FILL_BOTTOM 540
#define BARS_BOTTOM 600
#define BAR_HEIGHT 52
#define TICKS 614
#define CANVAS_TOP 226 /* the chart's canvas: from just above the sky to below the hours */
#define CANVAS_HEIGHT 420

static lv_obj_t *canvas, *now_line, *title, *range, *lead, *rest, *sun_times, *credit, *sun, *sun_glow, *moon, *moon_shadow;
static desk_day_t shown;
static int shown_minute = -1;
static int now_minute = -1; /* local, on this panel's clock; -1 before it is set */

static float x_of(float hour)
{
    return LEFT + (hour - 6.0f) / 18.0f * WIDTH;
}

static lv_color_t mix(uint32_t a, uint32_t b, float t)
{
    return lv_color_mix(lv_color_hex(b), lv_color_hex(a), (uint8_t)(fminf(fmaxf(t, 0), 1) * 255));
}

/* The sky through the day, around the real sunrise and sunset. */
static lv_color_t sky_at(float h, float sunrise, float sunset)
{
    const struct { float at; uint32_t colour; } stops[] = {
        {6.0f, 0x121633},          {sunrise - 0.5f, 0x2a2552}, {sunrise + 0.35f, 0xb8606a},
        {sunrise + 1.8f, 0x4a6fae}, {13.0f, 0x3f73b8},          {sunset - 1.1f, 0x5e6fa8},
        {sunset, 0xd07a4e},         {sunset + 1.1f, 0x3a2650},  {24.0f, 0x121633},
    };
    int n = sizeof stops / sizeof stops[0];
    if (h <= stops[0].at) {
        return lv_color_hex(stops[0].colour);
    }
    for (int i = 1; i < n; i++) {
        if (h <= stops[i].at) {
            float span = stops[i].at - stops[i - 1].at;
            return mix(stops[i - 1].colour, stops[i].colour, span > 0 ? (h - stops[i - 1].at) / span : 1);
        }
    }
    return lv_color_hex(stops[n - 1].colour);
}

/* The temperature line runs from cool blue to warm and back, as in the mockup. */
static lv_color_t line_at(float share)
{
    return share < 0.55f ? mix(0x8ab4ff, 0xffb86b, share / 0.55f) : mix(0xffb86b, 0x8ab4ff, (share - 0.55f) / 0.45f);
}

static void rect(lv_layer_t *layer, int x1, int y1, int x2, int y2, lv_color_t colour, lv_opa_t opa, int radius)
{
    lv_draw_rect_dsc_t dsc;
    lv_draw_rect_dsc_init(&dsc);
    dsc.bg_color = colour;
    dsc.bg_opa = opa;
    dsc.radius = radius;
    lv_area_t area = {x1, y1 - CANVAS_TOP, x2, y2 - CANVAS_TOP};
    lv_draw_rect(layer, &dsc, &area);
}

static void text_at(lv_layer_t *layer, const char *text, const lv_font_t *font, uint32_t colour, int x, int y,
                    lv_text_align_t align)
{
    lv_draw_label_dsc_t dsc;
    lv_draw_label_dsc_init(&dsc);
    dsc.text = text;
    dsc.text_local = 1; /* drawn later: copy it, the caller reuses its buffer */
    dsc.font = font;
    dsc.color = lv_color_hex(colour);
    dsc.align = align;
    y -= CANVAS_TOP;
    lv_area_t area = {x - 80, y, x + 80, y + font->line_height};
    if (align == LV_TEXT_ALIGN_LEFT) {
        area.x1 = x, area.x2 = x + 160;
    }
    lv_draw_label(layer, &dsc, &area);
}

/* Catmull-Rom through the hourly points, as the mockup's curve. */
static float curve_y(const float *ys, int n, float pos)
{
    int i = (int)floorf(pos);
    float t = pos - i;
    float p0 = ys[i > 0 ? i - 1 : 0], p1 = ys[i], p2 = ys[i + 1 < n ? i + 1 : n - 1],
          p3 = ys[i + 2 < n ? i + 2 : n - 1];
    return 0.5f * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                   (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
}

/* One pixel of the canvas (RGB888, stored blue first), over black. */
static void paint(lv_draw_buf_t *buf, int x, int y, lv_color_t colour, uint8_t opa)
{
    uint8_t *px = buf->data + (y - CANVAS_TOP) * buf->header.stride + x * 3;
    px[0] = colour.blue * opa / 255, px[1] = colour.green * opa / 255, px[2] = colour.red * opa / 255;
}

/* The curve's height at each pixel column, from the hourly temperatures. */
static void curve(int *ys_out, float *labels_y)
{
    float lo = shown.temperatures[0], hi = lo;
    for (int i = 1; i < shown.count; i++) {
        lo = fminf(lo, shown.temperatures[i]);
        hi = fmaxf(hi, shown.temperatures[i]);
    }
    float span = fmaxf(hi - lo, 4.0f);
    for (int i = 0; i < shown.count; i++) {
        labels_y[i] = CURVE_BOTTOM - (shown.temperatures[i] - lo) / span * (CURVE_BOTTOM - CURVE_TOP);
    }
    for (int x = 0; x < WIDTH; x++) {
        ys_out[x] = (int)curve_y(labels_y, shown.count, (float)x / WIDTH * (shown.count - 1));
    }
}

/* Many small shapes in one LVGL layer stall its task queue (it checks every
 * pair), so the sky band and the fill are painted straight into the pixels and
 * LVGL gets the rest in small batches. */
static void draw_chart(lv_draw_buf_t *buf)
{
    float sunrise = shown.sunrise_minute / 60.0f, sunset = shown.sunset_minute / 60.0f;
    static int ys[WIDTH];
    float points[DESK_DAY_POINTS];
    curve(ys, points);

    /* The sky band, and below the curve a warm glow fading out. */
    lv_color_t warm = lv_color_hex(0xffb86b);
    for (int x = 0; x < WIDTH; x++) {
        lv_color_t sky = sky_at(6.0f + (float)x / WIDTH * 18.0f, sunrise, sunset);
        for (int y = SKY_TOP; y < HORIZON; y++) {
            paint(buf, LEFT + x, y, sky, 190);
        }
        paint(buf, LEFT + x, HORIZON, lv_color_white(), 46);
        for (int y = ys[x]; y < FILL_BOTTOM; y++) {
            paint(buf, LEFT + x, y, warm, (uint8_t)(50 * (FILL_BOTTOM - y) / (FILL_BOTTOM - ys[x])));
        }
    }

    lv_layer_t layer;

    /* The sun's path, dotted. */
    lv_canvas_init_layer(canvas, &layer);
    for (int i = 0; i <= 44; i++) {
        float f = i / 44.0f;
        int x = (int)x_of(sunrise + (sunset - sunrise) * f);
        int y = HORIZON - (int)(sinf((float)M_PI * f) * ARC);
        rect(&layer, x - 2, y - 2, x + 2, y + 2, lv_color_hex(0xffecc8), 150, 2);
    }
    lv_canvas_finish_layer(canvas, &layer);

    /* The temperature line, cool to warm and back. */
    lv_canvas_init_layer(canvas, &layer);
    for (int x = 8; x < WIDTH; x += 8) {
        lv_draw_line_dsc_t line;
        lv_draw_line_dsc_init(&line);
        line.color = line_at((float)x / WIDTH);
        line.width = 5;
        line.round_start = line.round_end = 1;
        int to = x + 8 < WIDTH ? x : WIDTH - 1;
        line.p1.x = LEFT + x - 8, line.p1.y = ys[x - 8] - CANVAS_TOP;
        line.p2.x = LEFT + to, line.p2.y = ys[to] - CANVAS_TOP;
        lv_draw_line(&layer, &line);
    }
    lv_canvas_finish_layer(canvas, &layer);

    lv_canvas_init_layer(canvas, &layer);
    /* The warmest point and the start, labelled. */
    int peak = 0;
    for (int i = 1; i < shown.count; i++) {
        peak = shown.temperatures[i] > shown.temperatures[peak] ? i : peak;
    }
    char label[8];
    snprintf(label, sizeof label, "%d°", (int)lroundf(shown.temperatures[peak]));
    text_at(&layer, label, &instrument_28_bold, 0xffd9a8, (int)x_of(6 + peak), (int)points[peak] - 40,
            LV_TEXT_ALIGN_CENTER);
    snprintf(label, sizeof label, "%d°", (int)lroundf(shown.temperatures[0]));
    text_at(&layer, label, &instrument_24, 0x8ab4ff, LEFT, (int)points[0] - 34, LV_TEXT_ALIGN_LEFT);

    /* The chance of rain per hour. */
    for (int i = 0; i < shown.count; i++) {
        if (shown.rain[i] <= 0) {
            continue;
        }
        int x = (int)x_of(6 + i), h = shown.rain[i] * BAR_HEIGHT / 100;
        rect(&layer, x - 8, BARS_BOTTOM - h, x + 8, BARS_BOTTOM, mix(0x6f60ea, 0xb4a9ff, shown.rain[i] / 100.0f),
             LV_OPA_COVER, 3);
    }

    /* The hours along the bottom. */
    const char *ticks[] = {"06:00", "12:00", "18:00", "24:00"};
    for (int i = 0; i < 4; i++) {
        int x = (int)x_of(6 + 6 * i);
        text_at(&layer, ticks[i], &instrument_24, 0x7d7a8c, i == 0 ? x : (i == 3 ? x - 70 : x), TICKS,
                i == 0 ? LV_TEXT_ALIGN_LEFT : LV_TEXT_ALIGN_CENTER);
    }
    lv_canvas_finish_layer(canvas, &layer);
}

static void redraw_chart(void)
{
    lv_canvas_fill_bg(canvas, lv_color_black(), LV_OPA_COVER);
    if (shown.present && shown.count >= 2) {
        draw_chart(lv_canvas_get_draw_buf(canvas));
        lv_obj_invalidate(canvas);
    }
}

/* Now, as a dashed line on today's view; the sun on its arc while it is up,
 * else the moon above now. */
static void place_now(void)
{
    bool line = shown.present && shown.today && now_minute >= 360;
    if (line) {
        lv_obj_set_x(now_line, (int)x_of(now_minute / 60.0f));
    }
    lv_obj_set_flag(now_line, LV_OBJ_FLAG_HIDDEN, !line);

    float sunrise = shown.sunrise_minute / 60.0f, sunset = shown.sunset_minute / 60.0f;
    float now = now_minute / 60.0f;
    bool up = shown.present && shown.today && now_minute >= 0 && now > sunrise && now < sunset;
    if (up) {
        float f = (now - sunrise) / (sunset - sunrise);
        int x = (int)x_of(now), y = HORIZON - (int)(sinf((float)M_PI * f) * ARC);
        lv_obj_set_pos(sun, x - 9, y - 9);
        lv_obj_set_pos(sun_glow, x - 80, y - 80);
    }
    lv_obj_set_flag(sun, LV_OBJ_FLAG_HIDDEN, !up);
    lv_obj_set_flag(sun_glow, LV_OBJ_FLAG_HIDDEN, !up);

    bool night = shown.present && shown.today && now_minute >= 360 && !up;
    if (night) {
        int x = (int)x_of(now);
        lv_obj_set_pos(moon, x - 10, HORIZON - 70);
        lv_obj_set_pos(moon_shadow, x - 5, HORIZON - 74);
    }
    lv_obj_set_flag(moon, LV_OBJ_FLAG_HIDDEN, !night);
    lv_obj_set_flag(moon_shadow, LV_OBJ_FLAG_HIDDEN, !night);
}

static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

static void tick(lv_timer_t *timer)
{
    desk_day_t now = desk_day();
    bool changed = now.version != shown.version;
    if (changed) {
        shown = now;
        redraw_chart();
        char text[40];
        upper(text, sizeof text, now.present ? now.title : "Your day");
        lv_label_set_text(title, text);
        if (now.present) {
            lv_label_set_text_fmt(range, "HIGH %d°  ·  LOW %d°", now.high, now.low);
            lv_label_set_text(lead, now.lead);
            lv_label_set_text(rest, now.rest);
            lv_label_set_text_fmt(sun_times, "Sunrise %s  ·  Sunset %s", now.sunrise, now.sunset);
            lv_label_set_text(credit, now.credit);
        } else {
            lv_label_set_text(range, "");
            lv_label_set_text(lead, "No forecast yet");
            lv_label_set_text(rest, "");
        }
    }

    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (tv.tv_sec > 1700000000) {
        time_t local = tv.tv_sec + desk_clock().utc_offset;
        struct tm t;
        gmtime_r(&local, &t);
        now_minute = t.tm_hour * 60 + t.tm_min;
    }
    if (changed || now_minute != shown_minute) {
        shown_minute = now_minute;
        place_now();
    }
}

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_label_set_text(label, "");
    return label;
}

static lv_obj_t *dot(lv_obj_t *parent, int size, uint32_t colour)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_set_size(obj, size, size);
    lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(obj, lv_color_hex(colour), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
    return obj;
}

void screen_day_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    title = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_align(title, LV_ALIGN_TOP_LEFT, 36, 24);
    range = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(range, 2, 0);
    lv_obj_align(range, LV_ALIGN_TOP_RIGHT, -36, 24);

    lead = text(screen, &instrument_40, 0xffffff);
    lv_obj_align(lead, LV_ALIGN_TOP_LEFT, 36, 84);
    rest = text(screen, &instrument_40, 0x9b98a8);
    lv_obj_align(rest, LV_ALIGN_TOP_LEFT, 36, 136);

    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(720, CANVAS_HEIGHT, LV_COLOR_FORMAT_RGB888, 0));
    lv_obj_set_pos(canvas, 0, CANVAS_TOP);
    lv_canvas_fill_bg(canvas, lv_color_black(), LV_OPA_COVER);

    static lv_point_precise_t ends[] = {{0, SKY_TOP + 4}, {0, BARS_BOTTOM}};
    now_line = lv_line_create(screen);
    lv_line_set_points(now_line, ends, 2);
    lv_obj_set_style_line_color(now_line, lv_color_white(), 0);
    lv_obj_set_style_line_opa(now_line, 115, 0);
    lv_obj_set_style_line_width(now_line, 2, 0);
    lv_obj_set_style_line_dash_width(now_line, 4, 0);
    lv_obj_set_style_line_dash_gap(now_line, 6, 0);
    lv_obj_add_flag(now_line, LV_OBJ_FLAG_HIDDEN);

    /* The sun: a warm glow and a pale disc; the moon: a disc with a shadow. */
    sun_glow = lv_image_create(screen);
    lv_image_set_src(sun_glow, &glow_round);
    lv_obj_set_style_image_recolor(sun_glow, lv_color_hex(0xffb86b), 0);
    lv_obj_set_style_image_recolor_opa(sun_glow, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sun_glow, 200, 0);
    lv_obj_add_flag(sun_glow, LV_OBJ_FLAG_HIDDEN);
    sun = dot(screen, 18, 0xfff2d6);
    moon = dot(screen, 20, 0xc9c4ee);
    moon_shadow = dot(screen, 18, 0x0f0f1a);

    sun_times = text(screen, &instrument_24, 0x8a8794);
    lv_obj_align(sun_times, LV_ALIGN_BOTTOM_LEFT, 36, -22);
    credit = text(screen, &instrument_24, 0x7d7a8c);
    lv_obj_align(credit, LV_ALIGN_BOTTOM_RIGHT, -36, -22);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
