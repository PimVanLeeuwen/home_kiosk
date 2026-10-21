/* The Now panel's clock (plan.md M20): the time, the weather in words, the next
 * sunset or sunrise, and light from the top in the colour of the sky outside
 * (the hub picks it, app/desk_clock.py). When rain is due in the next two hours,
 * it shows as bars along the bottom, one per five minutes from now, taller and
 * lighter as the rain gets heavier; on a dry day the time stands alone. */

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

#define MARGIN 36       /* as the header on every panel screen */
#define DRY_TOP 230     /* the time's top on a dry day: the group sits in the middle */
#define WET_TOP 160     /* and with rain due, higher, to make room for the bars */
#define WEATHER_BELOW 164
#define LINE_BELOW 238  /* the rain line under the weather, on a dry day */
#define WET_LINE_Y 500  /* the rain line above the bars */
#define BASE 652        /* the bars stand on this line */
#define TALLEST 100     /* a bar at TOP_MM and above */
#define SHORTEST 10     /* a bar with the least rain that counts */
#define AXIS_Y 664
#define TOP_MM 3.0f     /* rain this heavy fills a bar */
#define WET_MM 0.1f

static lv_obj_t *bars, *clock_label, *weather_row, *temperature, *weather, *date, *sun, *rain_line, *sky,
    *halo, *axis[3];
EXT_RAM_BSS_ATTR static desk_clock_t shown;
static int shown_minute = -1;
static int shown_hour = -1;

/* Without the hub's colour: by the hour, as the glow at the top of Home does. */
static void sky_by_hour(int hour, uint32_t *colour, lv_opa_t *opa)
{
    if (hour >= 21 || hour < 6) {
        *colour = 0x463caa, *opa = 120; /* night: deep blue */
    } else if (hour < 9) {
        *colour = 0xb46eaa, *opa = 100; /* dawn: rose */
    } else if (hour < 17) {
        *colour = 0x7d98c4, *opa = 95; /* day: a soft sky blue */
    } else {
        *colour = 0xc86e78, *opa = 95; /* dusk: warm */
    }
}

static void set_sky(int hour)
{
    uint32_t colour;
    lv_opa_t opa;
    if (shown.has_sky) {
        colour = shown.sky_colour, opa = shown.sky_opacity;
    } else {
        sky_by_hour(hour, &colour, &opa);
    }
    lv_obj_set_style_image_recolor(sky, lv_color_hex(colour), 0);
    lv_obj_set_style_image_opa(sky, opa, 0);
    lv_obj_set_style_image_recolor(halo, lv_color_hex(colour), 0);
}

/* "Sunset 18:41" as "SUNSET 18:41", for the quiet labels at the top. */
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

/* The bars, drawn straight onto the bars object's layer, only when rain is due. */
static void draw_bars(lv_event_t *event)
{
    if (!shown.wet || shown.rain_count == 0) {
        return;
    }
    lv_layer_t *layer = lv_event_get_layer(event);
    float step = (720.0f - 2 * MARGIN) / shown.rain_count;
    lv_opa_t opa = shown.stale ? LV_OPA_50 : LV_OPA_COVER;

    lv_draw_line_dsc_t base;
    lv_draw_line_dsc_init(&base);
    base.color = lv_color_white();
    base.opa = 40;
    base.width = 2;
    base.p1.x = MARGIN;
    base.p1.y = BASE + 3;
    base.p2.x = 720 - MARGIN;
    base.p2.y = BASE + 3;
    lv_draw_line(layer, &base);

    for (int i = 0; i < shown.rain_count; i++) {
        float mm = shown.rain[i];
        if (mm < WET_MM) {
            continue;
        }
        float share = sqrtf(fminf(mm, TOP_MM)) / sqrtf(TOP_MM);
        int height = SHORTEST + (int)(share * (TALLEST - SHORTEST));
        lv_draw_rect_dsc_t bar;
        lv_draw_rect_dsc_init(&bar);
        bar.bg_color = mix(lv_color_hex(0x5f86c4), lv_color_hex(0xc4dcff), share);
        bar.bg_opa = opa;
        bar.radius = 4;
        lv_area_t area = {
            .x1 = MARGIN + (int32_t)(i * step) + 4,
            .y1 = BASE - height,
            .x2 = MARGIN + (int32_t)((i + 1) * step) - 4,
            .y2 = BASE,
        };
        lv_draw_rect(layer, &bar, &area);
    }
}

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    return label;
}

/* The time and weather in the middle on a dry day; higher, with the bars below, when rain is due. */
static void lay_out(bool wet)
{
    int top = wet ? WET_TOP : DRY_TOP;
    lv_obj_align(clock_label, LV_ALIGN_TOP_MID, 0, top);
    lv_obj_align(halo, LV_ALIGN_TOP_LEFT, 360 - 80, top + 85 - 80);
    lv_obj_align(weather_row, LV_ALIGN_TOP_MID, 0, top + WEATHER_BELOW);
    if (wet) {
        lv_obj_align(rain_line, LV_ALIGN_TOP_LEFT, MARGIN, WET_LINE_Y);
    } else {
        lv_obj_align(rain_line, LV_ALIGN_TOP_MID, 0, top + LINE_BELOW);
    }
    for (int i = 0; i < 3; i++) {
        if (wet) {
            lv_obj_remove_flag(axis[i], LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(axis[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
}

static void tick(lv_timer_t *timer)
{
    desk_clock_t now = desk_clock();
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (now.version != shown.version) {
        shown = now;
        char text_up[64];
        upper(text_up, sizeof text_up, now.present ? now.date : "Connecting to the hub");
        lv_label_set_text(date, text_up);
        upper(text_up, sizeof text_up, now.sun);
        lv_label_set_text(sun, text_up);
        if (now.has_temperature) {
            lv_label_set_text_fmt(temperature, "%d°", now.temperature);
        } else {
            lv_label_set_text(temperature, "");
        }
        lv_label_set_text_fmt(weather, "%s%s", now.has_temperature && now.description[0] ? "·  " : "",
                              now.description);
        lv_label_set_text(rain_line, now.rain_line);
        lv_obj_set_style_text_color(rain_line, lv_color_hex(now.wet ? 0x9cc0f0 : 0x8a8794), 0);
        for (int i = 0; i < 3; i++) {
            lv_label_set_text(axis[i], now.rain_axis[i]);
        }
        lay_out(now.wet);
        time_t local_now = tv.tv_sec + now.utc_offset;
        struct tm t_now;
        gmtime_r(&local_now, &t_now);
        set_sky(t_now.tm_hour);
        lv_obj_invalidate(bars);
    }

    /* The time, once the hub has set the clock. */
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

    /* Light from the top in the colour of the sky, and a soft glow behind the
     * time: alpha-only images, coloured here, shown at 2x. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);

    halo = lv_image_create(screen);
    lv_image_set_src(halo, &glow_round);
    lv_image_set_scale(halo, 256 * 520 / 160); /* 520 px across, fading out around the time */
    lv_obj_set_style_image_recolor_opa(halo, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(halo, 50, 0);
    set_sky(12);

    bars = lv_obj_create(screen);
    lv_obj_remove_style_all(bars);
    lv_obj_set_size(bars, 720, 720);
    lv_obj_add_event_cb(bars, draw_bars, LV_EVENT_DRAW_MAIN, NULL);

    date = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(date, 2, 0);
    lv_obj_align(date, LV_ALIGN_TOP_LEFT, MARGIN, 24);
    sun = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(sun, 2, 0);
    lv_obj_align(sun, LV_ALIGN_TOP_RIGHT, -MARGIN, 24);
    lv_label_set_text(sun, "");

    /* The font's own spacing, as in the design: centred, it shifts a little with
     * the minutes, which reads better than fixed-width digits ("1 1"). */
    clock_label = text(screen, &instrument_clock, 0xffffff);
    lv_label_set_text(clock_label, "--:--");

    /* The temperature in white, the weather in words softer beside it. */
    weather_row = lv_obj_create(screen);
    lv_obj_remove_style_all(weather_row);
    lv_obj_set_size(weather_row, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(weather_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(weather_row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
    lv_obj_set_style_pad_column(weather_row, 14, 0);
    temperature = text(weather_row, &instrument_40, 0xffffff);
    weather = text(weather_row, &instrument_40, 0x9b98a8);
    lv_label_set_text(temperature, "");
    lv_label_set_text(weather, "");

    rain_line = text(screen, &instrument_28_bold, 0x8a8794);
    lv_label_set_text(rain_line, "");

    /* Under the bars: now on the left, an hour on in the middle, two hours on the right. */
    const lv_align_t where[3] = {LV_ALIGN_TOP_LEFT, LV_ALIGN_TOP_MID, LV_ALIGN_TOP_RIGHT};
    const int32_t x[3] = {MARGIN, 0, -MARGIN};
    for (int i = 0; i < 3; i++) {
        axis[i] = text(screen, &instrument_24, 0x8a8794);
        lv_label_set_text(axis[i], "");
        lv_obj_align(axis[i], where[i], x[i], AXIS_Y);
    }

    lay_out(false);
    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
