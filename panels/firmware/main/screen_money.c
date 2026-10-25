/* The House panel's Money screen (plan.md M20, the design of 2026-10-10, adapted
 * 2026-10-23): the portfolio's gain over the chosen period, large, in percentages only
 * (no amounts reach the panel); the gain line edge to edge, glowing, with a fill fading
 * down under it and its best point marked; and a switch for 1W, 1M, 1Y and All that turns
 * on the panel itself (nothing is sent). Today's change is in the pill. Words and points
 * from the hub (app/desk_money.py).
 *
 * The chart is drawn into a canvas when the answer or the period changes: its fill is
 * painted straight into the pixels, column by column, the line on top. */

#include "screen_money.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "arrive.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define CHART_TOP 250
#define CHART_W 720
#define CHART_H 300
#define TOP_PAD 50   /* room above the line for the best point's label */
#define SWITCH_TOP 612

#define GREEN 0x5fd39c
#define RED 0xff7d7d
#define VIOLET 0x7c6cf2

static lv_obj_t *sky, *title, *pill, *pill_text, *change, *span, *chart, *high, *buttons[DESK_MONEY_PERIODS];
static char chosen[4] = "1M"; /* the period on show, kept across answers */
EXT_RAM_BSS_ATTR static desk_money_t shown; /* off the LVGL task's small stack */

static int chosen_index(void)
{
    for (int i = 0; i < shown.period_count; i++) {
        if (strcmp(shown.periods[i].key, chosen) == 0) {
            return i;
        }
    }
    return shown.period_count > 0 ? 0 : -1;
}

static int32_t y_of(uint16_t point)
{
    return TOP_PAD + (1000 - point) * (CHART_H - TOP_PAD - 20) / 1000;
}

static void draw_chart(int which)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(chart);
    memset(buf->data, 0, buf->header.stride * CHART_H);
    const typeof(shown.periods[0]) *p = &shown.periods[which];
    if (p->count < 2) {
        lv_obj_invalidate(chart);
        return;
    }
    uint32_t colour = p->up ? GREEN : RED;
    uint8_t r = (colour >> 16) & 0xff, g = (colour >> 8) & 0xff, b = colour & 0xff;

    /* The fill: under the line, strongest at the line, gone at the bottom. */
    for (int32_t x = 0; x < CHART_W; x++) {
        float at = (float)x * (p->count - 1) / (CHART_W - 1);
        int i = (int)at;
        float f = at - i;
        uint16_t v = i + 1 < p->count ? (uint16_t)(p->points[i] * (1 - f) + p->points[i + 1] * f) : p->points[i];
        int32_t top = y_of(v);
        for (int32_t y = top; y < CHART_H; y++) {
            uint8_t a = (uint8_t)(90 * (CHART_H - y) / (CHART_H - top + 1));
            uint8_t *px = buf->data + y * buf->header.stride + x * 4;
            px[0] = b, px[1] = g, px[2] = r, px[3] = a;
        }
    }

    lv_layer_t layer;
    lv_canvas_init_layer(chart, &layer);
    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.color = lv_color_hex(colour);
    line.round_start = line.round_end = 1;
    for (int pass = 0; pass < 2; pass++) {
        line.width = pass ? 4 : 12; /* a soft glow first, the line on it */
        line.opa = pass ? LV_OPA_COVER : 50;
        for (int i = 1; i < p->count; i++) {
            line.p1.x = (i - 1) * (CHART_W - 1) / (p->count - 1), line.p1.y = y_of(p->points[i - 1]);
            line.p2.x = i * (CHART_W - 1) / (p->count - 1), line.p2.y = y_of(p->points[i]);
            lv_draw_line(&layer, &line);
        }
    }
    if (p->high_at >= 0) {
        lv_draw_rect_dsc_t dot;
        lv_draw_rect_dsc_init(&dot);
        dot.radius = LV_RADIUS_CIRCLE;
        dot.bg_color = lv_color_white();
        dot.border_color = lv_color_hex(colour), dot.border_width = 3;
        int32_t cx = p->high_at * (CHART_W - 1) / (p->count - 1), cy = y_of(p->points[p->high_at]);
        lv_area_t area = {.x1 = cx - 8, .y1 = cy - 8, .x2 = cx + 8, .y2 = cy + 8};
        lv_draw_rect(&layer, &dot, &area);
    }
    lv_canvas_finish_layer(chart, &layer);
    lv_obj_invalidate(chart);
}

static void show_period(void)
{
    int which = chosen_index();
    if (which < 0) {
        return;
    }
    const typeof(shown.periods[0]) *p = &shown.periods[which];
    char caps[48];
    ui_upper(caps, sizeof caps, p->label);
    char words[96];
    snprintf(words, sizeof words, "%s · %s", shown.title, caps);
    lv_label_set_text(title, words);
    lv_label_set_text(change, p->change);
    lv_obj_set_style_text_color(change, lv_color_hex(p->up ? GREEN : RED), 0);
    snprintf(words, sizeof words, "%s to %s, deposits left out", p->from, p->to);
    lv_label_set_text(span, words);
    draw_chart(which);

    /* "high +5.3%" over the best point, kept on the screen. */
    lv_obj_set_flag(high, LV_OBJ_FLAG_HIDDEN, p->high_at < 0);
    if (p->high_at >= 0) {
        snprintf(words, sizeof words, "high %s", p->high);
        lv_label_set_text(high, words);
        lv_obj_update_layout(high);
        int32_t x = p->high_at * (CHART_W - 1) / (p->count - 1) - lv_obj_get_width(high) / 2;
        int32_t room = CHART_W - LEFT - lv_obj_get_width(high);
        lv_obj_set_pos(high, x < LEFT ? LEFT : x > room ? room : x, CHART_TOP + y_of(p->points[p->high_at]) - 44);
    }
    for (int i = 0; i < DESK_MONEY_PERIODS; i++) {
        bool here = i < shown.period_count;
        lv_obj_set_flag(buttons[i], LV_OBJ_FLAG_HIDDEN, !here);
        if (here) {
            bool on = i == which;
            lv_label_set_text(lv_obj_get_child(buttons[i], 0), shown.periods[i].key);
            lv_obj_set_style_bg_opa(buttons[i], on ? 60 : 0, 0);
            lv_obj_set_style_text_color(lv_obj_get_child(buttons[i], 0), lv_color_hex(on ? 0xffffff : 0x8a8794), 0);
        }
    }
}

static void on_period(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    if (i < shown.period_count) {
        snprintf(chosen, sizeof chosen, "%s", shown.periods[i].key);
        show_period();
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_money_version() == version) {
        return;
    }
    desk_money_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(pill_text, shown.today);
    lv_obj_set_flag(pill, LV_OBJ_FLAG_HIDDEN, shown.today[0] == '\0');
    uint32_t tone = shown.today_up ? GREEN : RED;
    lv_obj_set_style_border_color(pill, lv_color_hex(tone), 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(tone), 0);
    show_period();
}

void screen_money_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(VIOLET), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_one_line(screen, &instrument_24, 0x8a8794, 420);
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

    change = ui_text(screen, &instrument_52_bold, GREEN);
    arrive_count(change);
    lv_obj_set_pos(change, LEFT, 96);
    span = ui_one_line(screen, &instrument_24, 0x8a8794, WIDTH);
    lv_obj_set_pos(span, LEFT, 168);

    chart = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(chart, lv_draw_buf_create(CHART_W, CHART_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(chart)->data, 0, lv_canvas_get_draw_buf(chart)->header.stride * CHART_H);
    lv_obj_set_pos(chart, 0, CHART_TOP);
    arrive_draw_in(chart, CHART_W, CHART_H);
    high = ui_text(screen, &instrument_24, 0xf1eff7);
    lv_obj_add_flag(high, LV_OBJ_FLAG_HIDDEN);

    /* The switch: four equal parts, the chosen one lit. */
    lv_obj_t *bar = ui_plain(screen);
    lv_obj_set_size(bar, WIDTH, 64);
    lv_obj_set_pos(bar, LEFT, SWITCH_TOP);
    lv_obj_set_style_radius(bar, 32, 0);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(bar, lv_color_hex(0x121119), 0);
    lv_obj_set_style_pad_all(bar, 6, 0);
    lv_obj_set_flex_flow(bar, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(bar, 6, 0);
    for (int i = 0; i < DESK_MONEY_PERIODS; i++) {
        lv_obj_t *button = buttons[i] = ui_plain(bar);
        lv_obj_set_height(button, LV_PCT(100));
        lv_obj_set_flex_grow(button, 1);
        lv_obj_set_style_radius(button, 26, 0);
        lv_obj_set_style_bg_color(button, lv_color_white(), 0);
        lv_obj_add_flag(button, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_add_event_cb(button, on_period, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        lv_obj_t *label = ui_text(button, &instrument_28_bold, 0x8a8794);
        lv_obj_center(label);
        lv_obj_add_flag(button, LV_OBJ_FLAG_HIDDEN);
    }

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
