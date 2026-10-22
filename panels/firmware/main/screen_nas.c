/* The House panel's NAS screen (plan.md M20, the instrument design of 2026-10-10): a gauge
 * for the fullest pool, violet running into amber, with ticks and a red mark where it would
 * alert; its size and runway below; then tiles for CPU and memory with the day as
 * sparklines, and for the disks (a dot each) with the UPS. Words and numbers from the hub
 * (app/desk_nas.py).
 *
 * The gauge and the sparklines are drawn once per answer into canvases: as LVGL shapes
 * they would be hundreds of objects in one layer. */

#include "screen_nas.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define GAUGE_W 520
#define GAUGE_H 290
#define GAUGE_TOP 76
#define R 200       /* the arc's outer radius */
#define ARC 26      /* its width */
#define TILE_TOP 470
#define TILE_GAP 14
#define TILE_W ((WIDTH - 2 * TILE_GAP) / 3)
#define TILE_H 200
#define SPARK_W (TILE_W - 36)
#define SPARK_H 56

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define RED 0xff6b6b
#define VIOLET 0x7c6cf2
#define LINE 0xb4a9ff

static lv_obj_t *sky, *title, *pill, *pill_text, *gauge, *percent, *size, *runway;
static lv_obj_t *cpu_value, *ram_value, *cpu_spark, *ram_spark, *disks_value, *disk_dots[DESK_NAS_DISKS], *ups;
EXT_RAM_BSS_ATTR static desk_nas_t shown; /* off the LVGL task's small stack */

/* Violet into lilac into amber, along the gauge (0..1). */
static lv_color_t along(float f)
{
    lv_color_t a = lv_color_hex(0x6f60ea), b = lv_color_hex(0xb4a9ff), c = lv_color_hex(AMBER);
    return f < 0.7f ? lv_color_mix(b, a, (uint8_t)(255 * f / 0.7f))
                    : lv_color_mix(c, b, (uint8_t)(255 * (f - 0.7f) / 0.3f));
}

static void arc(lv_layer_t *layer, float from, float to, int width, lv_color_t colour, lv_opa_t opa)
{
    lv_draw_arc_dsc_t dsc;
    lv_draw_arc_dsc_init(&dsc);
    dsc.center.x = GAUGE_W / 2, dsc.center.y = GAUGE_H - 20;
    dsc.radius = R + (width - ARC) / 2; /* a wider arc (the glow) straddles the same line */
    dsc.width = width;
    dsc.start_angle = from, dsc.end_angle = to;
    dsc.rounded = 1;
    dsc.color = colour, dsc.opa = opa;
    lv_draw_arc(layer, &dsc);
}

static void draw_gauge(int used, int limit)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(gauge);
    memset(buf->data, 0, buf->header.stride * GAUGE_H);
    lv_layer_t layer;
    lv_canvas_init_layer(gauge, &layer);
    const int cx = GAUGE_W / 2, cy = GAUGE_H - 20;

    /* Ticks outside the arc: every tenth of the way, the halves and the ends longer. */
    for (int i = 0; i <= 20; i++) {
        float a = (float)M_PI * (1 + i / 20.0f);
        int outer = R + (i % 5 ? 20 : 30);
        lv_draw_line_dsc_t tick;
        lv_draw_line_dsc_init(&tick);
        tick.color = lv_color_white();
        tick.opa = i % 5 ? 45 : 100;
        tick.width = 2;
        tick.p1.x = cx + (int)((R + 12) * cosf(a)), tick.p1.y = cy + (int)((R + 12) * sinf(a));
        tick.p2.x = cx + (int)(outer * cosf(a)), tick.p2.y = cy + (int)(outer * sinf(a));
        lv_draw_line(&layer, &tick);
    }

    arc(&layer, 180, 360, ARC, lv_color_white(), 18);
    used = used < 0 ? 0 : used > 100 ? 100 : used;
    float end = 180 + 180 * used / 100.0f;
    if (used > 0) {
        arc(&layer, 180, end, ARC + 22, lv_color_hex(VIOLET), 36); /* the glow */
        for (float a = 180; a < end; a += 2) {
            float to = a + 2 < end ? a + 2 : end;
            arc(&layer, a, to, ARC, along((a - 180) / 180), LV_OPA_COVER);
        }
    }

    /* Where the disk-space alert would open. */
    if (limit > 0 && limit < 100) {
        float a = (float)M_PI * (1 + limit / 100.0f);
        int at = R - ARC / 2;
        lv_draw_rect_dsc_t mark;
        lv_draw_rect_dsc_init(&mark);
        mark.radius = LV_RADIUS_CIRCLE;
        mark.bg_color = lv_color_hex(RED);
        mark.border_color = lv_color_black();
        mark.border_width = 3;
        lv_area_t area = {.x1 = cx + (int)(at * cosf(a)) - 9, .y1 = cy + (int)(at * sinf(a)) - 9};
        area.x2 = area.x1 + 18, area.y2 = area.y1 + 18;
        lv_draw_rect(&layer, &mark, &area);
    }
    lv_canvas_finish_layer(gauge, &layer);
    lv_obj_invalidate(gauge);
}

static void draw_spark(lv_obj_t *canvas, const uint8_t *points, int count)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    memset(buf->data, 0, buf->header.stride * SPARK_H);
    if (count >= 2) {
        int top = 1;
        for (int i = 0; i < count; i++) {
            top = points[i] > top ? points[i] : top;
        }
        lv_layer_t layer;
        lv_canvas_init_layer(canvas, &layer);
        lv_draw_line_dsc_t line;
        lv_draw_line_dsc_init(&line);
        line.color = lv_color_hex(LINE);
        line.width = 3;
        line.round_start = line.round_end = 1;
        for (int i = 1; i < count; i++) {
            line.p1.x = (i - 1) * (SPARK_W - 4) / (count - 1) + 2;
            line.p1.y = SPARK_H - 3 - points[i - 1] * (SPARK_H - 8) / top;
            line.p2.x = i * (SPARK_W - 4) / (count - 1) + 2;
            line.p2.y = SPARK_H - 3 - points[i] * (SPARK_H - 8) / top;
            lv_draw_line(&layer, &line);
        }
        lv_canvas_finish_layer(canvas, &layer);
    }
    lv_obj_invalidate(canvas);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_nas_version() == version) {
        return;
    }
    desk_nas_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    uint32_t tone = shown.warn ? AMBER : GREEN;
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(tone), 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(tone), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(shown.warn ? AMBER : VIOLET), 0);

    draw_gauge(shown.used_pct, shown.limit_pct);
    lv_label_set_text_fmt(percent, "%d", shown.used_pct);
    lv_label_set_text(size, shown.size);
    lv_label_set_text(runway, shown.runway);
    lv_obj_set_flag(runway, LV_OBJ_FLAG_HIDDEN, shown.runway[0] == '\0');

    lv_label_set_text_fmt(cpu_value, "%d%%", shown.cpu);
    lv_label_set_text_fmt(ram_value, "%d%%", shown.ram);
    draw_spark(cpu_spark, shown.cpu_points, shown.cpu_count);
    draw_spark(ram_spark, shown.ram_points, shown.ram_count);
    lv_label_set_text(disks_value, shown.disks_line);
    for (int i = 0; i < DESK_NAS_DISKS; i++) {
        lv_obj_set_flag(disk_dots[i], LV_OBJ_FLAG_HIDDEN, i >= shown.disk_count);
        uint32_t dot = shown.disks[i] ? GREEN : RED;
        lv_obj_set_style_bg_color(disk_dots[i], lv_color_hex(dot), 0);
        lv_obj_set_style_shadow_color(disk_dots[i], lv_color_hex(dot), 0);
    }
    lv_label_set_text(ups, shown.ups);
    lv_obj_set_style_text_color(ups, lv_color_hex(shown.ups_ok ? 0x8a8794 : AMBER), 0);
}

static lv_obj_t *tile(lv_obj_t *screen, int i, const char *name, lv_obj_t **value)
{
    lv_obj_t *box = ui_plain(screen);
    lv_obj_set_size(box, TILE_W, TILE_H);
    lv_obj_set_pos(box, LEFT + i * (TILE_W + TILE_GAP), TILE_TOP);
    lv_obj_set_style_radius(box, 18, 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(box, lv_color_hex(0x0d0d10), 0);
    lv_obj_set_style_border_width(box, 1, 0);
    lv_obj_set_style_border_color(box, lv_color_hex(0x1c1c22), 0);
    lv_obj_t *label = ui_text(box, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(label, 2, 0);
    lv_label_set_text(label, name);
    lv_obj_set_pos(label, 18, 16);
    *value = ui_text(box, &instrument_40, 0xf1eff7);
    lv_obj_set_pos(*value, 18, 50);
    return box;
}

static lv_obj_t *spark(lv_obj_t *box)
{
    lv_obj_t *canvas = lv_canvas_create(box);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(SPARK_W, SPARK_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(canvas)->data, 0, lv_canvas_get_draw_buf(canvas)->header.stride * SPARK_H);
    lv_obj_set_pos(canvas, 18, TILE_H - 18 - SPARK_H);
    return canvas;
}

void screen_nas_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* House's quiet violet from the top; amber while something about the NAS is open. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(VIOLET), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    pill = ui_plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 4, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_border_width(pill, 2, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 24);
    pill_text = ui_text(pill, &instrument_24, GREEN);
    lv_obj_set_style_text_letter_space(pill_text, 2, 0);

    gauge = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(gauge, lv_draw_buf_create(GAUGE_W, GAUGE_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(gauge)->data, 0, lv_canvas_get_draw_buf(gauge)->header.stride * GAUGE_H);
    lv_obj_set_pos(gauge, (720 - GAUGE_W) / 2, GAUGE_TOP);

    /* The number in the middle of the arc: "82" large, "%" beside it. */
    lv_obj_t *number = ui_plain(screen);
    lv_obj_set_size(number, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(number, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(number, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
    lv_obj_set_style_pad_column(number, 4, 0);
    lv_obj_align(number, LV_ALIGN_TOP_MID, 0, GAUGE_TOP + GAUGE_H - 20 - 96);
    percent = ui_text(number, &instrument_time, 0xf1eff7);
    lv_obj_t *sign = ui_text(number, &instrument_40, 0xb4b1c2);
    lv_label_set_text(sign, "%");
    lv_obj_set_style_pad_bottom(sign, 8, 0);

    size = ui_one_line(screen, &instrument_24, 0xc9c6d6, WIDTH);
    lv_obj_set_style_text_align(size, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(size, LEFT, GAUGE_TOP + GAUGE_H + 8);
    runway = ui_one_line(screen, &instrument_24, AMBER, WIDTH);
    lv_obj_set_style_text_align(runway, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(runway, LEFT, GAUGE_TOP + GAUGE_H + 40);

    cpu_spark = spark(tile(screen, 0, "CPU", &cpu_value));
    ram_spark = spark(tile(screen, 1, "MEMORY", &ram_value));
    lv_obj_t *disks = tile(screen, 2, "DISKS", &disks_value);
    lv_obj_t *row = ui_plain(disks);
    lv_obj_set_size(row, TILE_W - 36, 16);
    lv_obj_set_pos(row, 18, 116);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(row, 10, 0);
    for (int i = 0; i < DESK_NAS_DISKS; i++) {
        disk_dots[i] = ui_plain(row);
        lv_obj_set_size(disk_dots[i], 14, 14);
        lv_obj_set_style_radius(disk_dots[i], 7, 0);
        lv_obj_set_style_bg_opa(disk_dots[i], LV_OPA_COVER, 0);
        lv_obj_set_style_shadow_width(disk_dots[i], 8, 0);
        lv_obj_set_style_shadow_opa(disk_dots[i], 140, 0);
        lv_obj_add_flag(disk_dots[i], LV_OBJ_FLAG_HIDDEN);
    }
    ups = ui_one_line(disks, &instrument_24, 0x8a8794, TILE_W - 36);
    lv_obj_set_pos(ups, 18, TILE_H - 18 - lv_font_get_line_height(&instrument_24));

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
