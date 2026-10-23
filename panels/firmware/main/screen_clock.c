/* The Now panel's clock (plan.md M20), as Horizon (chosen 2026-10-23): the sky of the
 * moment fills the panel, from the zenith down to a horizon line, in the colours the hub
 * picks for the light outside and the weather (app/desk_clock.py); the sun by day or the
 * moon by night, in its phase, sits on its arc at the time it is, over a dotted path;
 * stars on a clear night. The time and the weather in words stand in the sky. When rain
 * is due in the next two hours it hangs under the horizon as bars, one per five minutes,
 * longer and lighter as the rain gets heavier; on a dry day a line says until when, with
 * the sun's times below.
 *
 * The scene is drawn into one canvas when the hub's answer changes (every 30 s or so),
 * so the sun moves in small steps and nothing animates; the text is labels on top. */

#include "screen_clock.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_clock);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define SIZE 720
#define MARGIN 36       /* as the header on every panel screen */
#define HORIZON 476     /* the horizon line's height */
#define TIME_TOP 96
#define WEATHER_TOP 262
#define DRY_LINE_Y 540  /* "Dry until ..." in the middle of the ground */
#define WET_LINE_Y 568  /* "Rain from ..." under the bars */
#define FOOT_Y 624      /* the sun's times, or the bars' clock */
#define LONGEST 72      /* a bar at TOP_MM and above */
#define SHORTEST 8      /* a bar with the least rain that counts */
#define TOP_MM 3.0f     /* rain this heavy fills a bar */
#define WET_MM 0.1f

static lv_obj_t *scene, *clock_label, *weather_row, *temperature, *weather, *date, *sun, *rain_line, *axis[3],
    *rise_label, *set_label;
EXT_RAM_BSS_ATTR static desk_clock_t shown;
static int shown_minute = -1;
static int shown_hour = -1;

typedef struct {
    uint8_t r, g, b;
} rgb_t;

static rgb_t rgb(uint32_t hex)
{
    return (rgb_t){(hex >> 16) & 0xff, (hex >> 8) & 0xff, hex & 0xff};
}

static rgb_t blend(rgb_t a, rgb_t b, float t)
{
    return (rgb_t){(uint8_t)(a.r + (b.r - a.r) * t), (uint8_t)(a.g + (b.g - a.g) * t),
                   (uint8_t)(a.b + (b.b - a.b) * t)};
}

static lv_color_t colour_of(rgb_t c)
{
    return lv_color_make(c.r, c.g, c.b);
}

/* The sky's colours: the hub's, or by the hour when it has none (an older hub). */
static void sky_colours(int hour, rgb_t *top, rgb_t *mid, rgb_t *low)
{
    if (shown.has_horizon) {
        *top = rgb(shown.sky_top), *mid = rgb(shown.sky_mid), *low = rgb(shown.sky_low);
    } else if (hour >= 21 || hour < 6) {
        *top = rgb(0x05060f), *mid = rgb(0x0d1230), *low = rgb(0x1b2350);
    } else if (hour < 9 || hour >= 17) {
        *top = rgb(0x1a1030), *mid = rgb(0x5a2d52), *low = rgb(0xb47458);
    } else {
        *top = rgb(0x0f1b36), *mid = rgb(0x2f4f8a), *low = rgb(0x7b97c8);
    }
}

/* The sky at a height: zenith to the middle colour over the upper half, then to the horizon. */
static rgb_t sky_at(int32_t y, rgb_t top, rgb_t mid, rgb_t low)
{
    float t = (float)y / HORIZON;
    return t < 0.55f ? blend(top, mid, t / 0.55f) : blend(mid, low, (t - 0.55f) / 0.45f);
}

/* The arc the sun and moon ride: from the left of the horizon, over, to the right. */
static void on_arc(float t, float *x, float *y)
{
    const float x0 = 40, y0 = HORIZON, cx = 360, cy = 250, x1 = 680, y1 = HORIZON;
    float u = 1 - t;
    *x = u * u * x0 + 2 * u * t * cx + t * t * x1;
    *y = u * u * y0 + 2 * u * t * cy + t * t * y1;
}

static void disc(lv_layer_t *layer, float x, float y, int r, rgb_t c, lv_opa_t opa)
{
    lv_draw_rect_dsc_t dsc;
    lv_draw_rect_dsc_init(&dsc);
    dsc.radius = LV_RADIUS_CIRCLE;
    dsc.bg_color = colour_of(c);
    dsc.bg_opa = opa;
    lv_area_t area = {.x1 = (int32_t)x - r, .y1 = (int32_t)y - r, .x2 = (int32_t)x + r, .y2 = (int32_t)y + r};
    lv_draw_rect(layer, &dsc, &area);
}

static void draw_scene(int hour)
{
    rgb_t top, mid, low;
    sky_colours(hour, &top, &mid, &low);
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(scene);

    /* The sky, row by row, and under the horizon the ground: its glow fading to black. */
    for (int32_t y = 0; y < SIZE; y++) {
        rgb_t c = y < HORIZON ? sky_at(y, top, mid, low)
                              : blend(blend(low, rgb(0), 0.88f), rgb(0), fminf(1.0f, (y - HORIZON) / 90.0f));
        uint8_t *row = buf->data + y * buf->header.stride;
        for (int32_t x = 0; x < SIZE; x++) {
            row[3 * x] = c.b, row[3 * x + 1] = c.g, row[3 * x + 2] = c.r;
        }
    }

    lv_layer_t layer;
    lv_canvas_init_layer(scene, &layer);
    if (shown.stars) { /* the same few stars every night */
        static const int16_t stars[][3] = {{90, 80, 2},   {610, 120, 2}, {530, 60, 1},  {160, 350, 2}, {640, 340, 2},
                                           {250, 40, 1},  {420, 30, 2},  {70, 230, 1},  {690, 220, 1}, {330, 70, 1},
                                           {580, 280, 1}, {120, 150, 1}, {470, 150, 1}, {30, 400, 1},  {700, 420, 1}};
        for (size_t i = 0; i < sizeof stars / sizeof stars[0]; i++) {
            disc(&layer, stars[i][0], stars[i][1], stars[i][2], rgb(0xffffff), (lv_opa_t)(90 + 30 * (i % 3)));
        }
    }

    /* The body's path, dotted. */
    for (int i = 1; i < 40; i++) {
        float x, y;
        on_arc(i / 40.0f, &x, &y);
        disc(&layer, x, y, 2, rgb(0xffffff), 34);
    }

    /* The sun, or the moon in its phase, where it is now. */
    float at = (shown.has_horizon ? shown.at : (hour >= 6 && hour < 18 ? (hour - 6) * 1000 / 12 : 500)) / 1000.0f;
    float bx, by;
    on_arc(at, &bx, &by);
    bool moon = shown.has_horizon ? shown.moon : (hour < 6 || hour >= 18);
    lv_opa_t veil = shown.veiled ? 150 : LV_OPA_COVER;
    if (!moon) {
        disc(&layer, bx, by, 70, rgb(0xffd9a0), shown.veiled ? 16 : 30);
        disc(&layer, bx, by, 44, rgb(0xffd9a0), shown.veiled ? 24 : 44);
        disc(&layer, bx, by, 26, rgb(0xffe7c2), veil);
    } else {
        disc(&layer, bx, by, 52, rgb(0xc8d0ff), shown.veiled ? 12 : 26);
        disc(&layer, bx, by, 21, rgb(0xe3e7ff), veil);
        /* Its shadow: a disc in the sky's colour, shifted by how much is lit (left while
         * waxing, right while waning), gone at full moon. */
        float f = (shown.has_horizon ? shown.moon_phase : 500) / 1000.0f;
        float lit = (1 - cosf(2 * (float)M_PI * f)) / 2;
        if (lit < 0.97f) {
            float shift = 2 * 21 * lit * (f < 0.5f ? -1 : 1);
            disc(&layer, bx + shift, by, 22, sky_at((int32_t)by, top, mid, low), LV_OPA_COVER);
        }
    }

    /* The horizon. */
    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.color = colour_of(blend(low, rgb(0xffffff), 0.35f));
    line.opa = 150;
    line.width = 2;
    line.p1.x = 0, line.p1.y = HORIZON;
    line.p2.x = SIZE, line.p2.y = HORIZON;
    lv_draw_line(&layer, &line);

    /* The coming rain, hanging under the horizon. */
    if (shown.wet && shown.rain_count > 0) {
        float step = (SIZE - 2.0f * MARGIN) / shown.rain_count;
        for (int i = 0; i < shown.rain_count; i++) {
            float mm = shown.rain[i];
            if (mm < WET_MM) {
                continue;
            }
            float share = sqrtf(fminf(mm, TOP_MM)) / sqrtf(TOP_MM);
            lv_draw_rect_dsc_t bar;
            lv_draw_rect_dsc_init(&bar);
            bar.bg_color = colour_of(blend(rgb(0x5f86c4), rgb(0xc4dcff), share));
            bar.bg_opa = shown.stale ? LV_OPA_50 : LV_OPA_COVER;
            bar.radius = 4;
            lv_area_t area = {.x1 = MARGIN + (int32_t)(i * step) + 3, .y1 = HORIZON + 4,
                              .x2 = MARGIN + (int32_t)((i + 1) * step) - 3,
                              .y2 = HORIZON + 4 + SHORTEST + (int32_t)(share * (LONGEST - SHORTEST))};
            lv_draw_rect(&layer, &bar, &area);
        }
    }
    lv_canvas_finish_layer(scene, &layer);
    lv_obj_invalidate(scene);
}

/* The words under the horizon: the rain line and the bars' clock when rain is due; else
 * until when it stays dry and, by day, the sun's times. */
static void lay_out(void)
{
    bool wet = shown.wet;
    if (wet) {
        lv_obj_align(rain_line, LV_ALIGN_TOP_LEFT, MARGIN, WET_LINE_Y);
    } else {
        lv_obj_align(rain_line, LV_ALIGN_TOP_MID, 0, DRY_LINE_Y);
    }
    for (int i = 0; i < 3; i++) {
        lv_obj_set_flag(axis[i], LV_OBJ_FLAG_HIDDEN, !wet);
    }
    bool day = shown.has_horizon && !shown.moon && shown.rise[0];
    lv_obj_set_flag(rise_label, LV_OBJ_FLAG_HIDDEN, wet || !day);
    lv_obj_set_flag(set_label, LV_OBJ_FLAG_HIDDEN, wet || !day);
}

static void tick(lv_timer_t *timer)
{
    desk_clock_t now = desk_clock();
    struct timeval tv;
    gettimeofday(&tv, NULL);
    time_t local_now = tv.tv_sec + now.utc_offset;
    struct tm t_now;
    gmtime_r(&local_now, &t_now);
    if (now.version != shown.version) {
        shown = now;
        char text_up[64];
        ui_upper(text_up, sizeof text_up, now.present ? now.date : "Connecting to the hub");
        lv_label_set_text(date, text_up);
        ui_upper(text_up, sizeof text_up, now.sun);
        lv_label_set_text(sun, text_up);
        if (now.has_temperature) {
            lv_label_set_text_fmt(temperature, "%d°", now.temperature);
        } else {
            lv_label_set_text(temperature, "");
        }
        lv_label_set_text_fmt(weather, "%s%s", now.has_temperature && now.description[0] ? "·  " : "",
                              now.description);
        lv_label_set_text(rain_line, now.rain_line);
        lv_obj_set_style_text_color(rain_line, lv_color_hex(now.wet ? 0x9cc0f0 : 0xa6adc8), 0);
        for (int i = 0; i < 3; i++) {
            lv_label_set_text(axis[i], now.rain_axis[i]);
        }
        lv_label_set_text_fmt(rise_label, "Sunrise %s", now.rise);
        lv_label_set_text_fmt(set_label, "Sunset %s", now.set);
        lay_out();
        draw_scene(t_now.tm_hour);
    }

    /* The time, once the hub has set the clock. */
    if (!shown.present || tv.tv_sec < 1700000000) {
        return;
    }
    if (t_now.tm_min == shown_minute) {
        return;
    }
    shown_minute = t_now.tm_min;
    if (t_now.tm_hour != shown_hour && !shown.has_horizon) {
        draw_scene(t_now.tm_hour); /* by the hour, without the hub's sky */
    }
    shown_hour = t_now.tm_hour;
    lv_label_set_text_fmt(clock_label, "%02d:%02d", t_now.tm_hour, t_now.tm_min);
}

static lv_obj_t *quiet(lv_obj_t *screen, lv_align_t align, int32_t x, int32_t y)
{
    lv_obj_t *label = ui_text(screen, &instrument_24, 0x9a9fb8);
    lv_obj_align(label, align, x, y);
    return label;
}

void screen_clock_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* The whole scene in one opaque canvas: the sky, the body, the horizon, the rain. */
    scene = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(scene, lv_draw_buf_create(SIZE, SIZE, LV_COLOR_FORMAT_RGB888, 0));
    memset(lv_canvas_get_draw_buf(scene)->data, 0, lv_canvas_get_draw_buf(scene)->header.stride * SIZE);
    lv_obj_set_pos(scene, 0, 0);

    date = ui_text(screen, &instrument_24, 0xc4c8de);
    lv_obj_set_style_text_letter_space(date, 2, 0);
    lv_obj_align(date, LV_ALIGN_TOP_LEFT, MARGIN, 24);
    sun = ui_text(screen, &instrument_24, 0xc4c8de);
    lv_obj_set_style_text_letter_space(sun, 2, 0);
    lv_obj_align(sun, LV_ALIGN_TOP_RIGHT, -MARGIN, 24);
    lv_label_set_text(sun, "");

    /* The font's own spacing, as in the design: centred, it shifts a little with
     * the minutes, which reads better than fixed-width digits ("1 1"). */
    clock_label = ui_text(screen, &instrument_clock, 0xffffff);
    lv_label_set_text(clock_label, "--:--");
    lv_obj_align(clock_label, LV_ALIGN_TOP_MID, 0, TIME_TOP);

    /* The temperature in white, the weather in words softer beside it. */
    weather_row = ui_plain(screen);
    lv_obj_set_size(weather_row, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(weather_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(weather_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
    lv_obj_set_style_pad_column(weather_row, 14, 0);
    lv_obj_align(weather_row, LV_ALIGN_TOP_MID, 0, WEATHER_TOP);
    temperature = ui_text(weather_row, &instrument_40, 0xffffff);
    weather = ui_text(weather_row, &instrument_40, 0xd6dbef);

    rain_line = ui_text(screen, &instrument_28_bold, 0xa6adc8);

    /* Under the bars: now on the left, an hour on in the middle, two hours on the right. */
    axis[0] = quiet(screen, LV_ALIGN_TOP_LEFT, MARGIN, FOOT_Y);
    axis[1] = quiet(screen, LV_ALIGN_TOP_MID, 0, FOOT_Y);
    axis[2] = quiet(screen, LV_ALIGN_TOP_RIGHT, -MARGIN, FOOT_Y);
    rise_label = quiet(screen, LV_ALIGN_TOP_LEFT, MARGIN, FOOT_Y);
    set_label = quiet(screen, LV_ALIGN_TOP_RIGHT, -MARGIN, FOOT_Y);

    lay_out();
    draw_scene(12);
    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
