/* The Now panel's clock (plan.md M20): the time inside a ring of the next two
 * hours of rain, one segment per five minutes from the top (now) clockwise,
 * longer and lighter as the rain gets heavier; the rain in words below.
 * Drawn as on the hub's Home (web/src/components/weather/RainRing.tsx). */

#include "screen_clock.h"

#include <math.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"

LV_FONT_DECLARE(instrument_clock);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);
LV_IMAGE_DECLARE(glow_round);

#define CX 360
#define CY 356
#define R 236           /* where the segments start: the time fits inside */
#define LONGEST 50      /* a segment at TOP_MM and above */
#define SHORTEST_WET 16 /* a segment with the least rain that counts */
#define DRY 9           /* a dry segment */
#define TOP_MM 3.0f     /* rain this heavy fills a segment */
#define WET_MM 0.1f

static lv_obj_t *ring, *clock_label, *temperature, *weather, *place, *date, *rain_line, *sky;
EXT_RAM_BSS_ATTR static desk_clock_t shown;
static int shown_minute = -1;
static int shown_hour = -1;

/* The light from the top follows the sky, as the glow at the top of Home does
 * (web/src/lib/sky.ts), stronger here: it should fall on the desk. */
static void set_sky(int hour)
{
    uint32_t colour;
    lv_opa_t opa;
    if (hour >= 21 || hour < 6) {
        colour = 0x463caa, opa = 120; /* night: deep blue */
    } else if (hour < 9) {
        colour = 0xb46eaa, opa = 100; /* dawn: rose */
    } else if (hour < 17) {
        colour = 0x7c6cf2, opa = 85; /* day: violet */
    } else {
        colour = 0xc86e78, opa = 95; /* dusk: warm */
    }
    lv_obj_set_style_image_recolor(sky, lv_color_hex(colour), 0);
    lv_obj_set_style_image_opa(sky, opa, 0);
}

/* "De Bilt" as "DE BILT", for the quiet labels at the top. */
static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

static lv_color_t mix(lv_color_t a, lv_color_t b, float t)
{
    return lv_color_mix(b, a, (uint8_t)(t * 255));
}

/* The segments, drawn straight onto the ring object's layer. */
static void draw_ring(lv_event_t *event)
{
    lv_layer_t *layer = lv_event_get_layer(event);
    int count = shown.rain_count > 0 ? shown.rain_count : 24;
    float step = 360.0f / count;
    float gap = fminf(1.6f, step * 0.12f);

    for (int i = 0; i < count; i++) {
        float mm = i < shown.rain_count ? shown.rain[i] : 0.0f;
        bool wet = mm >= WET_MM;
        float share = wet ? sqrtf(fminf(mm, TOP_MM)) / sqrtf(TOP_MM) : 0.0f;
        int length = wet ? SHORTEST_WET + (int)(share * (LONGEST - SHORTEST_WET)) : DRY;

        lv_draw_arc_dsc_t arc;
        lv_draw_arc_dsc_init(&arc);
        arc.center.x = CX;
        arc.center.y = CY;
        arc.radius = R + length;
        arc.width = length;
        /* LVGL counts degrees clockwise from 3 o'clock, 0 to 360; the ring starts
         * at 12 o'clock, which is 270. A negative angle draws a full circle. */
        arc.start_angle = (lv_value_precise_t)fmodf(i * step + gap + 270.0f, 360.0f);
        arc.end_angle = (lv_value_precise_t)fmodf((i + 1) * step - gap + 270.0f, 360.0f);
        arc.rounded = 0;
        arc.color = wet ? mix(lv_color_hex(0x6f60ea), lv_color_hex(0xc3b9ff), share) : lv_color_hex(0x2a2930);
        arc.opa = shown.stale ? LV_OPA_50 : LV_OPA_COVER;
        lv_draw_arc(layer, &arc);
    }

    /* Now, at the top. */
    lv_draw_line_dsc_t tick;
    lv_draw_line_dsc_init(&tick);
    tick.color = lv_color_white();
    tick.width = 5;
    tick.round_start = tick.round_end = 1;
    /* In the gap at 12 o'clock, just outside the ring's start, as on Home. */
    tick.p1.x = CX;
    tick.p1.y = CY - R - 4;
    tick.p2.x = CX;
    tick.p2.y = CY - R - 24;
    lv_draw_line(layer, &tick);
}

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    return label;
}

static void tick(lv_timer_t *timer)
{
    desk_clock_t now = desk_clock();
    if (now.version != shown.version) {
        shown = now;
        char text_up[64];
        upper(text_up, sizeof text_up, now.present ? now.place : "Connecting to the hub");
        lv_label_set_text_fmt(place, "%s%s", text_up, now.present ? "  ·  BUIENRADAR" : "");
        upper(text_up, sizeof text_up, now.date);
        lv_label_set_text(date, text_up);
        if (now.has_temperature) {
            lv_label_set_text_fmt(temperature, "%d°", now.temperature);
        } else {
            lv_label_set_text(temperature, "");
        }
        lv_label_set_text_fmt(weather, "%s%s", now.has_temperature && now.description[0] ? "·  " : "",
                              now.description);
        lv_label_set_text(rain_line, now.rain_line);
        lv_obj_set_style_text_color(rain_line, lv_color_hex(now.wet ? 0xb4a9ff : 0x8a8794), 0);
        lv_obj_invalidate(ring);
    }

    /* The time, once the hub has set the clock. */
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (!shown.present || tv.tv_sec < 1700000000) {
        return;
    }
    time_t local = tv.tv_sec + shown.utc_offset;
    struct tm t;
    gmtime_r(&local, &t);
    if (t.tm_min == shown_minute) {
        return;
    }
    shown_minute = t.tm_min;
    if (t.tm_hour != shown_hour) {
        shown_hour = t.tm_hour;
        set_sky(t.tm_hour);
    }
    lv_label_set_text_fmt(clock_label, "%02d:%02d", t.tm_hour, t.tm_min);
}

void screen_clock_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Light from the top in the colour of the time of day, and a soft glow
     * behind the time: alpha-only images, coloured here, shown at 2x. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    set_sky(12);

    lv_obj_t *halo = lv_image_create(screen);
    lv_image_set_src(halo, &glow_round);
    lv_image_set_scale(halo, 256 * 520 / 160); /* 520 px across: it fades out inside the ring */
    lv_obj_align(halo, LV_ALIGN_TOP_LEFT, CX - 80, CY - 80);
    lv_obj_set_style_image_recolor(halo, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(halo, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(halo, 60, 0);

    ring = lv_obj_create(screen);
    lv_obj_remove_style_all(ring);
    lv_obj_set_size(ring, 720, 720);
    lv_obj_add_event_cb(ring, draw_ring, LV_EVENT_DRAW_MAIN, NULL);

    place = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(place, 2, 0);
    lv_obj_align(place, LV_ALIGN_TOP_LEFT, 36, 24);
    date = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(date, 2, 0);
    lv_obj_align(date, LV_ALIGN_TOP_RIGHT, -36, 24);

    /* The font's own spacing, as in the design: centred, it shifts a little with
     * the minutes, which reads better than fixed-width digits ("1 1"). */
    clock_label = text(screen, &instrument_clock, 0xffffff);
    lv_label_set_text(clock_label, "--:--");
    lv_obj_align(clock_label, LV_ALIGN_TOP_MID, 0, CY - 112);

    /* The temperature in white, Buienradar's words softer beside it. */
    lv_obj_t *weather_row = lv_obj_create(screen);
    lv_obj_remove_style_all(weather_row);
    lv_obj_set_size(weather_row, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(weather_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(weather_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
    lv_obj_set_style_pad_column(weather_row, 14, 0);
    temperature = text(weather_row, &instrument_40, 0xffffff);
    weather = text(weather_row, &instrument_40, 0x9b98a8);
    lv_label_set_text(temperature, "");
    lv_label_set_text(weather, "");
    lv_obj_align(weather_row, LV_ALIGN_TOP_MID, 0, CY + 52);

    rain_line = text(screen, &instrument_28_bold, 0x8a8794);
    lv_obj_align(rain_line, LV_ALIGN_BOTTOM_MID, 0, -22);
    lv_label_set_text(rain_line, "");

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
