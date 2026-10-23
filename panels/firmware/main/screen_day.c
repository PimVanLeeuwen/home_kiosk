/* The Now panel's day view (plan.md M20, redrawn as Y1 on 2026-10-23): the temperature from
 * 06:00 to midnight as a curve across the middle, the night hours a slightly darker field with
 * sunrise and sunset as quiet dotted lines, the chance of rain per hour underneath, a now line,
 * and a sentence on the day. The sky band and the sun's arc went: the clock (Horizon) has the
 * sky. Values come ready-made from the hub (app/desk.py); the now line follows the panel's own
 * clock.
 *
 * The chart is drawn once into a canvas when the hub's answer changes: drawn from a draw
 * event, LVGL repeats every shape for every strip of every frame, which held the display lock
 * for seconds. The now line sits on top as an object. */

#include "screen_day.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

/* The chart: hours 6 to 24 across; the night field and the sun lines span it all. */
#define LEFT 36
#define WIDTH 648
#define CHART_TOP 236  /* the night field's top, and the sun lines' labels */
#define CURVE_TOP 300
#define CURVE_BOTTOM 470
#define FILL_BOTTOM 528
#define BARS_BOTTOM 600
#define BAR_HEIGHT 56
#define TICKS 614
#define CANVAS_TOP 226 /* the chart's canvas: from just above the chart to below the hours */
#define CANVAS_HEIGHT 420
#define NIGHT 0x0c0e1d

static lv_obj_t *canvas, *now_line, *title, *range, *lead, *rest, *credit;
EXT_RAM_BSS_ATTR static desk_day_t shown;
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
    EXT_RAM_BSS_ATTR static int ys[WIDTH];
    float points[DESK_DAY_POINTS];
    curve(ys, points);

    /* Night: a slightly darker field before sunrise and after sunset, half an hour soft at
     * each edge; and below the curve a warm glow fading out. */
    lv_color_t warm = lv_color_hex(0xffb86b), night = lv_color_hex(NIGHT);
    for (int x = 0; x < WIDTH; x++) {
        float h = 6.0f + (float)x / WIDTH * 18.0f;
        float dark = fmaxf(fminf((sunrise - h) / 1.0f + 0.5f, 1), fminf((h - sunset) / 1.0f + 0.5f, 1));
        if (dark > 0) {
            /* Faded out at the top and the bottom too, so it reads as dusk, not a box. */
            for (int y = CHART_TOP + 20; y < FILL_BOTTOM + 30; y++) {
                float edge = fminf(fminf((y - CHART_TOP - 20) / 70.0f, (FILL_BOTTOM + 30 - y) / 70.0f), 1);
                paint(buf, LEFT + x, y, night, (uint8_t)(255 * fminf(dark, 1) * edge));
            }
        }
        for (int y = ys[x]; y < FILL_BOTTOM; y++) {
            paint(buf, LEFT + x, y, warm, (uint8_t)(50 * (FILL_BOTTOM - y) / (FILL_BOTTOM - ys[x])));
        }
    }

    lv_layer_t layer;

    /* Sunrise and sunset: quiet dotted lines, their times at the top. */
    lv_canvas_init_layer(canvas, &layer);
    const float at[2] = {sunrise, sunset};
    const char *names[2] = {shown.sunrise, shown.sunset};
    for (int k = 0; k < 2; k++) {
        if (at[k] <= 6.2f || at[k] >= 23.8f) {
            continue;
        }
        int x = (int)x_of(at[k]);
        for (int y = CHART_TOP + 34; y < BARS_BOTTOM; y += 10) {
            rect(&layer, x - 1, y, x, y + 3, lv_color_hex(0xffb27a), 90, 0);
        }
        char words[24];
        snprintf(words, sizeof words, "%s %s", k ? "sunset" : "sunrise", names[k]);
        text_at(&layer, words, &instrument_24, 0xc99877, x, CHART_TOP, LV_TEXT_ALIGN_CENTER);
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

/* Now, as a solid line on today's view (the sun's lines are the dotted ones). */
static void place_now(void)
{
    bool line = shown.present && shown.today && now_minute >= 360;
    if (line) {
        lv_obj_set_x(now_line, (int)x_of(now_minute / 60.0f));
    }
    lv_obj_set_flag(now_line, LV_OBJ_FLAG_HIDDEN, !line);
}

static void tick(lv_timer_t *timer)
{
    desk_day_t now = desk_day();
    bool changed = now.version != shown.version;
    if (changed) {
        shown = now;
        redraw_chart();
        char text[40];
        ui_upper(text, sizeof text, now.present ? now.title : "Your day");
        lv_label_set_text(title, text);
        if (now.present) {
            lv_label_set_text_fmt(range, "HIGH %d°  ·  LOW %d°", now.high, now.low);
            lv_label_set_text(lead, now.lead);
            lv_label_set_text(rest, now.rest);
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

void screen_day_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_align(title, LV_ALIGN_TOP_LEFT, 36, 24);
    range = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(range, 2, 0);
    lv_obj_align(range, LV_ALIGN_TOP_RIGHT, -36, 24);

    lead = ui_text(screen, &instrument_40, 0xffffff);
    lv_obj_align(lead, LV_ALIGN_TOP_LEFT, 36, 84);
    rest = ui_text(screen, &instrument_40, 0x9b98a8);
    lv_obj_align(rest, LV_ALIGN_TOP_LEFT, 36, 136);

    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(720, CANVAS_HEIGHT, LV_COLOR_FORMAT_RGB888, 0));
    lv_obj_set_pos(canvas, 0, CANVAS_TOP);
    lv_canvas_fill_bg(canvas, lv_color_black(), LV_OPA_COVER);

    static lv_point_precise_t ends[] = {{0, CHART_TOP + 34}, {0, BARS_BOTTOM}};
    now_line = lv_line_create(screen);
    lv_line_set_points(now_line, ends, 2);
    lv_obj_set_style_line_color(now_line, lv_color_white(), 0);
    lv_obj_set_style_line_opa(now_line, 150, 0);
    lv_obj_set_style_line_width(now_line, 2, 0);
    lv_obj_add_flag(now_line, LV_OBJ_FLAG_HIDDEN);

    credit = ui_text(screen, &instrument_24, 0x7d7a8c);
    lv_obj_align(credit, LV_ALIGN_BOTTOM_RIGHT, -36, -22);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
