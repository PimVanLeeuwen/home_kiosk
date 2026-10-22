/* The Home panel's air (plan.md M17), as approved on 2026-10-21 and as the hub's
 * Air card: the living room's temperature large on the left with humidity, fine
 * dust and the sensor's own verdict below it; CO2 on the right as a ring over
 * three quarters of a circle (400 to 2000 ppm, gaps at 800 and 1200) in the
 * colour of its word; below, CO2 over the last 8 hours. The wording, rounding
 * and colours come from the hub (app/desk_home.py, air_screen).
 *
 * The curve is painted straight into a canvas when the hub's answer changes:
 * a hundred small shapes in one LVGL layer would stall its task queue. */

#include "screen_air.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_clock);
LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define CX 540           /* the ring's centre */
#define CY 262
#define R 118
#define RING_START 135   /* degrees, clockwise from 3 o'clock */
#define RING_SPAN 270
#define CHART_TOP 500    /* the curve's canvas */
#define CHART_HEIGHT 150
#define CHART_WIDTH (720 - 2 * LEFT)
#define CURVE_LOW 350    /* ppm at the canvas's bottom and top */
#define CURVE_HIGH 1600

static lv_obj_t *ring, *canvas, *header, *outside, *temperature, *humidity, *dust, *quality, *co2, *unit,
    *word, *axis_start, *axis_end;
EXT_RAM_BSS_ATTR static desk_air_t shown; /* off the LVGL task's small stack */

static int angle(int share) /* share 0 to 1000 along the ring */
{
    return RING_START + RING_SPAN * share / 1000;
}

static void arc(lv_layer_t *layer, int from, int to, lv_color_t colour, lv_opa_t opa)
{
    lv_draw_arc_dsc_t dsc;
    lv_draw_arc_dsc_init(&dsc);
    dsc.center.x = CX;
    dsc.center.y = CY;
    dsc.radius = R + 10;
    dsc.width = 20;
    dsc.rounded = 1;
    dsc.start_angle = from % 360;
    dsc.end_angle = to % 360;
    dsc.color = colour;
    dsc.opa = opa;
    lv_draw_arc(layer, &dsc);
}

/* The ring: the track with gaps at 800 and 1200 ppm, filled to now, a white dot at its end. */
static void draw_ring(lv_event_t *event)
{
    if (!shown.present || !shown.has_co2) {
        return;
    }
    lv_layer_t *layer = lv_event_get_layer(event);
    lv_opa_t opa = shown.stale ? LV_OPA_50 : LV_OPA_COVER;
    arc(layer, RING_START, RING_START + RING_SPAN, lv_color_hex(0x24232b), LV_OPA_COVER);
    for (int i = 0; i < 2; i++) { /* the gaps: 800 ppm is a quarter of the way, 1200 a half */
        float a = angle(i == 0 ? 250 : 500) * (float)M_PI / 180;
        lv_draw_line_dsc_t gap;
        lv_draw_line_dsc_init(&gap);
        gap.color = lv_color_black();
        gap.width = 4;
        /* Across the track only (it runs from R - 10 to R + 10), not out over the glow. */
        gap.p1.x = CX + (int)((R - 11) * cosf(a));
        gap.p1.y = CY + (int)((R - 11) * sinf(a));
        gap.p2.x = CX + (int)((R + 11) * cosf(a));
        gap.p2.y = CY + (int)((R + 11) * sinf(a));
        lv_draw_line(layer, &gap);
    }
    int end = angle(shown.ring > 3 ? shown.ring : 3);
    arc(layer, RING_START, end, lv_color_hex(shown.colour), opa);

    float a = end * (float)M_PI / 180;
    lv_draw_rect_dsc_t dot;
    lv_draw_rect_dsc_init(&dot);
    dot.bg_color = lv_color_white();
    dot.radius = LV_RADIUS_CIRCLE;
    lv_area_t area = {.x1 = CX + (int)(R * cosf(a)) - 13, .y1 = CY + (int)(R * sinf(a)) - 13};
    area.x2 = area.x1 + 26;
    area.y2 = area.y1 + 26;
    lv_draw_rect(layer, &dot, &area);
}

/* One pixel of the canvas (RGB888, stored blue first), over black. */
static void paint(lv_draw_buf_t *buf, int x, int y, lv_color_t colour, uint8_t opa)
{
    if (x < 0 || x >= CHART_WIDTH || y < 0 || y >= CHART_HEIGHT) {
        return;
    }
    uint8_t *px = buf->data + y * buf->header.stride + x * 3;
    px[0] = colour.blue * opa / 255, px[1] = colour.green * opa / 255, px[2] = colour.red * opa / 255;
}

static int curve_y(float ppm)
{
    float share = (fminf(fmaxf(ppm, CURVE_LOW), CURVE_HIGH) - CURVE_LOW) / (CURVE_HIGH - CURVE_LOW);
    return (int)((CHART_HEIGHT - 3) * (1 - share)) + 1;
}

/* The curve: a soft fill under it in the word's colour, the line on top, dashes at 800 and 1200. */
static void draw_curve(void)
{
    lv_canvas_fill_bg(canvas, lv_color_black(), LV_OPA_COVER);
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    int n = shown.history_count;
    if (n < 2) {
        lv_obj_invalidate(canvas);
        return;
    }
    lv_color_t colour = lv_color_hex(shown.colour), line = lv_color_hex(0x3a3944);
    int dashes[2] = {curve_y(800), curve_y(1200)};
    for (int x = 0; x < CHART_WIDTH; x++) {
        if ((x / 8) % 2 == 0) {
            for (int d = 0; d < 2; d++) {
                paint(buf, x, dashes[d], line, 255);
            }
        }
        float at = (float)x / (CHART_WIDTH - 1) * (n - 1);
        int i = (int)at;
        float t = at - i;
        float ppm = shown.history[i] + (i + 1 < n ? (shown.history[i + 1] - shown.history[i]) * t : 0);
        int y = curve_y(ppm);
        for (int fill = y + 2; fill < CHART_HEIGHT; fill++) {
            paint(buf, x, fill, colour, 34);
        }
        for (int thick = -2; thick <= 1; thick++) {
            paint(buf, x, y + thick, colour, shown.stale ? 128 : 255);
        }
    }
    lv_obj_invalidate(canvas);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_air_version() == version) {
        return;
    }
    shown = desk_air();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    char caps[48];
    snprintf(caps, sizeof caps, "%s  ·  AIR", shown.room);
    ui_upper(caps, sizeof caps, caps);
    lv_label_set_text(header, caps);
    ui_upper(caps, sizeof caps, shown.outside);
    lv_label_set_text(outside, caps);
    lv_label_set_text(temperature, shown.temperature);
    lv_label_set_text_fmt(humidity, "%s%s", shown.humidity, shown.humidity[0] ? "  humidity" : "");
    /* Instrument Sans has no µ or ³, so the measure is named instead of its unit. */
    lv_label_set_text_fmt(dust, "%s%s", shown.pm25, shown.pm25[0] ? "  PM2.5 fine dust" : "");
    lv_label_set_text_fmt(quality, "%s%s", shown.quality[0] ? "Sensor says: " : "", shown.quality);
    lv_obj_set_flag(co2, LV_OBJ_FLAG_HIDDEN, !shown.has_co2);
    lv_obj_set_flag(unit, LV_OBJ_FLAG_HIDDEN, !shown.has_co2);
    lv_label_set_text_fmt(co2, "%d", shown.co2);
    lv_label_set_text(word, shown.word);
    lv_obj_set_style_text_color(word, lv_color_hex(shown.colour), 0);
    lv_obj_set_flag(axis_start, LV_OBJ_FLAG_HIDDEN, shown.history_count < 2);
    lv_obj_set_flag(axis_end, LV_OBJ_FLAG_HIDDEN, shown.history_count < 2);
    lv_obj_invalidate(ring);
    draw_curve();
}

void screen_air_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* The room's warm light from the top, as the Home panel's other screens. */
    lv_obj_t *sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0xffb46b), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 70, 0);

    header = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_obj_set_pos(header, LEFT, 30);
    outside = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(outside, 2, 0);
    lv_obj_align(outside, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    temperature = ui_text(screen, &instrument_clock, 0xffffff);
    lv_obj_set_pos(temperature, LEFT - 6, 104);
    humidity = ui_text(screen, &instrument_28_bold, 0xd8d6e0);
    lv_obj_set_pos(humidity, LEFT, 296);
    dust = ui_text(screen, &instrument_28_bold, 0xd8d6e0);
    lv_obj_set_pos(dust, LEFT, 340);
    quality = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_pos(quality, LEFT, 384);

    ring = lv_obj_create(screen);
    lv_obj_remove_style_all(ring);
    lv_obj_set_size(ring, 720, 720);
    lv_obj_remove_flag(ring, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(ring, draw_ring, LV_EVENT_DRAW_MAIN, NULL);
    co2 = ui_text(screen, &instrument_52_bold, 0xffffff);
    lv_obj_align(co2, LV_ALIGN_TOP_MID, CX - 360, CY - 40);
    unit = ui_text(screen, &instrument_24, 0x8a8794);
    lv_label_set_text(unit, "ppm CO2");
    lv_obj_align(unit, LV_ALIGN_TOP_MID, CX - 360, CY + 22);
    word = ui_text(screen, &instrument_28_bold, 0x8a8794);
    lv_obj_align(word, LV_ALIGN_TOP_MID, CX - 360, CY + R + 22);

    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(CHART_WIDTH, CHART_HEIGHT, LV_COLOR_FORMAT_RGB888, 0));
    lv_obj_set_pos(canvas, LEFT, CHART_TOP);
    lv_canvas_fill_bg(canvas, lv_color_black(), LV_OPA_COVER);
    axis_start = ui_text(screen, &instrument_24, 0x8a8794);
    lv_label_set_text(axis_start, "8 h ago");
    lv_obj_set_pos(axis_start, LEFT, CHART_TOP + CHART_HEIGHT + 12);
    axis_end = ui_text(screen, &instrument_24, 0x8a8794);
    lv_label_set_text(axis_end, "now");
    lv_obj_align(axis_end, LV_ALIGN_TOP_RIGHT, -LEFT, CHART_TOP + CHART_HEIGHT + 12);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
