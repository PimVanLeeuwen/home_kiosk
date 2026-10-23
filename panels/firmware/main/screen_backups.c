/* The House panel's Backups screen (plan.md M20, the design of 2026-10-10): a seal (green
 * while all is safe, amber with an open backup alert, red when the last run failed) beside
 * when the last run started, how long it took and what it copied, and the last restore
 * check; the NAS to Hetzner (encrypted) line with one light moving along it (chosen
 * 2026-10-22) and the Storage Box; and the nights as bars by how long each took, a slow
 * night amber, a failed one red, the last one bright. Words from the hub
 * (app/desk_backups.py).
 *
 * The seal and the bars are drawn once per answer into canvases; only the light moves. */

#include "screen_backups.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define SEAL 160
#define HERO_TOP 92
#define FLOW_TOP 300
#define BARS_TOP 420
#define BARS_H 180
#define LIGHT 12

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define RED 0xff6b6b
#define VIOLET 0x7c6cf2

static lv_obj_t *sky, *title, *pill, *pill_text, *seal, *time_label, *line, *restore, *box;
static lv_obj_t *flow_line, *light, *bars, *count_label, *slow_label, *last_label;
EXT_RAM_BSS_ATTR static desk_backups_t shown; /* off the LVGL task's small stack */

static void circle(lv_layer_t *layer, int r, lv_color_t fill, lv_opa_t fill_opa, lv_color_t edge, int edge_w)
{
    lv_draw_rect_dsc_t dsc;
    lv_draw_rect_dsc_init(&dsc);
    dsc.radius = LV_RADIUS_CIRCLE;
    dsc.bg_color = fill, dsc.bg_opa = fill_opa;
    dsc.border_color = edge, dsc.border_width = edge_w, dsc.border_opa = edge_w ? LV_OPA_COVER : 0;
    lv_area_t area = {.x1 = SEAL / 2 - r, .y1 = SEAL / 2 - r, .x2 = SEAL / 2 + r, .y2 = SEAL / 2 + r};
    lv_draw_rect(layer, &dsc, &area);
}

/* The seal: a soft halo, a dotted ring, a ring with its check (or a cross after a failed run). */
static void draw_seal(uint32_t colour, bool failed)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(seal);
    memset(buf->data, 0, buf->header.stride * SEAL);
    lv_layer_t layer;
    lv_canvas_init_layer(seal, &layer);
    lv_color_t c = lv_color_hex(colour);
    circle(&layer, SEAL / 2 - 2, c, 30, c, 0);
    for (int i = 0; i < 40; i++) {
        lv_draw_arc_dsc_t dot;
        lv_draw_arc_dsc_init(&dot);
        dot.center.x = dot.center.y = SEAL / 2;
        dot.radius = SEAL / 2 - 12, dot.width = 2;
        dot.start_angle = i * 9, dot.end_angle = i * 9 + 3.5f;
        dot.color = c, dot.opa = 120;
        lv_draw_arc(&layer, &dot);
    }
    circle(&layer, SEAL / 2 - 26, c, 40, c, 4);
    lv_draw_line_dsc_t mark;
    lv_draw_line_dsc_init(&mark);
    mark.color = c, mark.width = 9, mark.round_start = mark.round_end = 1;
    if (failed) {
        mark.p1.x = 58, mark.p1.y = 58, mark.p2.x = 102, mark.p2.y = 102;
        lv_draw_line(&layer, &mark);
        mark.p1.x = 102, mark.p1.y = 58, mark.p2.x = 58, mark.p2.y = 102;
        lv_draw_line(&layer, &mark);
    } else {
        mark.p1.x = 56, mark.p1.y = 82, mark.p2.x = 74, mark.p2.y = 100;
        lv_draw_line(&layer, &mark);
        mark.p1.x = 74, mark.p1.y = 100, mark.p2.x = 106, mark.p2.y = 64;
        lv_draw_line(&layer, &mark);
    }
    lv_canvas_finish_layer(seal, &layer);
    lv_obj_invalidate(seal);
}

/* One bar per night, by how long it took; the slowest night sets the scale. */
static int draw_bars(void)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(bars);
    memset(buf->data, 0, buf->header.stride * BARS_H);
    int count = shown.night_count, slowest = 1, last_slow = -1;
    for (int i = 0; i < count; i++) {
        slowest = shown.nights[i].seconds > slowest ? shown.nights[i].seconds : slowest;
        last_slow = shown.nights[i].state == 's' ? i : last_slow;
    }
    if (count > 0) {
        lv_layer_t layer;
        lv_canvas_init_layer(bars, &layer);
        int step = WIDTH / DESK_NIGHTS, bar = step - 6;
        int x0 = WIDTH - count * step; /* the latest night at the right edge */
        for (int i = 0; i < count; i++) {
            char state = shown.nights[i].state;
            bool last = i == count - 1;
            lv_draw_rect_dsc_t dsc;
            lv_draw_rect_dsc_init(&dsc);
            dsc.radius = 4;
            dsc.bg_color = lv_color_hex(state == 'f' ? RED : state == 's' ? AMBER : GREEN);
            dsc.bg_opa = state != 'o' || last ? LV_OPA_COVER : 110;
            int h = 6 + shown.nights[i].seconds * (BARS_H - 10) / slowest;
            lv_area_t area = {.x1 = x0 + i * step + 3, .y1 = BARS_H - h, .x2 = x0 + i * step + 3 + bar - 1,
                              .y2 = BARS_H - 1};
            lv_draw_rect(&layer, &dsc, &area);
        }
        lv_canvas_finish_layer(bars, &layer);
    }
    lv_obj_invalidate(bars);
    return last_slow < 0 ? -1 : (WIDTH - count * (WIDTH / DESK_NIGHTS)) + last_slow * (WIDTH / DESK_NIGHTS) +
                                    (WIDTH / DESK_NIGHTS) / 2;
}

/* The light slides from the NAS to Hetzner, fading in and out at the ends. */
static void move_light(void *obj, int32_t at)
{
    int32_t from = lv_obj_get_x(flow_line), length = lv_obj_get_width(flow_line);
    lv_obj_set_x(obj, from + length * at / 1000 - LIGHT / 2);
    int32_t edge = at < 150 ? at : at > 850 ? 1000 - at : 150;
    lv_obj_set_style_bg_opa(obj, (lv_opa_t)(edge * 255 / 150), 0);
    lv_obj_set_style_shadow_opa(obj, (lv_opa_t)(edge * 200 / 150), 0);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_backups_version() == version) {
        return;
    }
    desk_backups_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    uint32_t tone = !shown.ok ? RED : shown.warn ? AMBER : GREEN;
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(shown.warn ? AMBER : GREEN), 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(shown.warn ? AMBER : GREEN), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(tone == GREEN ? VIOLET : tone), 0);

    draw_seal(tone, !shown.ok);
    lv_label_set_text(time_label, shown.time);
    lv_label_set_text(line, shown.line);
    lv_label_set_text(restore, shown.restore);
    uint32_t restore_colour = shown.restore_tone == 'o' ? GREEN : shown.restore_tone == 'f' ? RED : 0x8a8794;
    lv_obj_set_style_text_color(restore, lv_color_hex(restore_colour), 0);
    lv_label_set_text(box, shown.box);

    int slow_x = draw_bars();
    lv_label_set_text_fmt(count_label, "%d night%s", shown.night_count, shown.night_count == 1 ? "" : "s");
    /* "slow" under the latest slow night, unless it would touch the words at either end:
     * the amber bar says it then. */
    lv_obj_update_layout(lv_obj_get_parent(slow_label));
    int32_t width = lv_obj_get_width(slow_label);
    int32_t x = LEFT + slow_x - width / 2;
    int32_t after_count = lv_obj_get_x(count_label) + lv_obj_get_width(count_label) + 16;
    int32_t before_last = lv_obj_get_x(last_label) - 16;
    bool fits = slow_x >= 0 && x >= after_count && x + width <= before_last;
    lv_obj_set_flag(slow_label, LV_OBJ_FLAG_HIDDEN, !fits);
    if (fits) {
        lv_obj_set_x(slow_label, x);
    }
}

static lv_obj_t *chip(lv_obj_t *screen, const char *words)
{
    lv_obj_t *obj = ui_plain(screen);
    lv_obj_set_size(obj, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(obj, 18, 0);
    lv_obj_set_style_pad_ver(obj, 8, 0);
    lv_obj_set_style_radius(obj, 22, 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(obj, lv_color_hex(0x121119), 0);
    lv_obj_set_style_border_width(obj, 1, 0);
    lv_obj_set_style_border_color(obj, lv_color_hex(0x2a2833), 0);
    lv_obj_t *label = ui_text(obj, &instrument_24, 0xf1eff7);
    lv_label_set_text(label, words);
    return obj;
}

void screen_backups_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

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

    /* The seal, and beside it when, how long, how much, and the restore check. */
    seal = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(seal, lv_draw_buf_create(SEAL, SEAL, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(seal)->data, 0, lv_canvas_get_draw_buf(seal)->header.stride * SEAL);
    lv_obj_set_pos(seal, LEFT, HERO_TOP);
    int text_x = LEFT + SEAL + 28, text_w = WIDTH - SEAL - 28;
    time_label = ui_text(screen, &instrument_time, 0xf1eff7);
    lv_obj_set_pos(time_label, text_x, HERO_TOP - 2);
    line = ui_one_line(screen, &instrument_24, 0xc9c6d6, text_w);
    lv_obj_set_pos(line, text_x, HERO_TOP + 80);
    restore = ui_one_line(screen, &instrument_24, 0x8a8794, text_w);
    lv_obj_set_pos(restore, text_x, HERO_TOP + 116);

    /* NAS to Hetzner, encrypted, with one light on its way. */
    lv_obj_t *from = chip(screen, "NAS");
    lv_obj_set_pos(from, LEFT, FLOW_TOP);
    lv_obj_t *to = chip(screen, "Hetzner · encrypted");
    lv_obj_align(to, LV_ALIGN_TOP_RIGHT, -LEFT, FLOW_TOP);
    lv_obj_update_layout(screen);
    int32_t line_x = lv_obj_get_x(from) + lv_obj_get_width(from) + 14;
    int32_t line_w = lv_obj_get_x(to) - 14 - line_x;
    int32_t mid = FLOW_TOP + lv_obj_get_height(from) / 2;
    flow_line = ui_plain(screen);
    lv_obj_set_size(flow_line, line_w, 2);
    lv_obj_set_pos(flow_line, line_x, mid - 1);
    lv_obj_set_style_bg_opa(flow_line, 90, 0);
    lv_obj_set_style_bg_color(flow_line, lv_color_hex(GREEN), 0);
    light = ui_plain(screen);
    lv_obj_set_size(light, LIGHT, LIGHT);
    lv_obj_set_y(light, mid - LIGHT / 2);
    lv_obj_set_style_radius(light, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(light, lv_color_hex(GREEN), 0);
    lv_obj_set_style_shadow_color(light, lv_color_hex(GREEN), 0);
    lv_obj_set_style_shadow_width(light, 14, 0);
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, light);
    lv_anim_set_exec_cb(&anim, move_light);
    lv_anim_set_values(&anim, 0, 1000);
    lv_anim_set_duration(&anim, 2600);
    lv_anim_set_repeat_delay(&anim, 1400);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_start(&anim);
    box = ui_one_line(screen, &instrument_24, 0x8a8794, WIDTH);
    lv_obj_set_style_text_align(box, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(box, LEFT, FLOW_TOP + 56);

    /* The nights, the latest on the right. */
    bars = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(bars, lv_draw_buf_create(WIDTH, BARS_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(bars)->data, 0, lv_canvas_get_draw_buf(bars)->header.stride * BARS_H);
    lv_obj_set_pos(bars, LEFT, BARS_TOP);
    int under = BARS_TOP + BARS_H + 8;
    count_label = ui_text(screen, &instrument_24, 0x7d7a8c);
    lv_obj_set_pos(count_label, LEFT, under);
    slow_label = ui_text(screen, &instrument_24, AMBER);
    lv_label_set_text(slow_label, "slow");
    lv_obj_set_y(slow_label, under);
    lv_obj_add_flag(slow_label, LV_OBJ_FLAG_HIDDEN);
    last_label = ui_text(screen, &instrument_24, 0x7d7a8c);
    lv_label_set_text(last_label, "Latest");
    lv_obj_align(last_label, LV_ALIGN_TOP_RIGHT, -LEFT, under);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
