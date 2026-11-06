/* The House panel's Stock screen (decided 2026-11-06, in place of the movers heat map):
 * one holding's last five trading days, a different one at random each time the screen
 * comes round (equal chances, never the same twice running), so a stock never changes
 * while it is on show. Its ticker and name, the week's change large and its price; today
 * and your gain in the pills, in percentages only. The line runs nearly edge to edge,
 * glowing, with a fill fading down under it, a dashed line at the close before the week,
 * the trading days apart with faint lines, the high and the low marked, and a ripple on
 * the latest price. Words and points from the hub (app/desk_stock.py).
 *
 * The chart is drawn into a canvas when the stock or the answer changes: the fill, the
 * dashes and the day lines painted straight into the pixels, the line on top. */

#include "screen_stock.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "esp_random.h"
#include "lvgl.h"
#include "arrive.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define CHART_TOP 196
#define CHART_W 720
#define CHART_H 420
#define TOP_PAD 60    /* room above the line for the high's label */
#define BOTTOM_PAD 56 /* and below it for the low's */
#define END_PAD 40    /* room right of the line for the latest price's ripple */
#define GLOW 12       /* how far the glow reaches either side of the line */
#define DAYS_TOP (CHART_TOP + CHART_H + 6)
#define DOTS_TOP 680
#define DOT 14
#define RIPPLE 46

#define GREEN 0x5fd39c
#define RED 0xff7d7d
#define VIOLET 0x7c6cf2
#define GREY 0x8a8794

static lv_obj_t *title, *pills, *today, *gain, *ticker, *name, *week, *price, *chart, *high, *low, *pulse,
    *ripple, *dot, *days[DESK_STOCK_DAYS], *dots[DESK_STOCKS];
static int picked = -1;
static char picked_ticker[16];
EXT_RAM_BSS_ATTR static desk_stock_t shown; /* off the LVGL task's small stack */

static int32_t x_of(int i, int count)
{
    return i * (CHART_W - 1 - END_PAD) / (count - 1);
}

static int32_t y_of(uint16_t point)
{
    return TOP_PAD + (1000 - point) * (CHART_H - TOP_PAD - BOTTOM_PAD) / 1000;
}

static void paint(lv_draw_buf_t *buf, int32_t x, int32_t y, uint32_t colour, uint8_t alpha)
{
    if (x < 0 || x >= CHART_W || y < 0 || y >= CHART_H) {
        return;
    }
    uint8_t *px = buf->data + y * buf->header.stride + x * 4;
    px[0] = colour & 0xff, px[1] = (colour >> 8) & 0xff, px[2] = (colour >> 16) & 0xff, px[3] = alpha;
}

/* White at `alpha` over what is painted there already. */
static void lighten(lv_draw_buf_t *buf, int32_t x, int32_t y, uint8_t alpha)
{
    if (x < 0 || x >= CHART_W || y < 0 || y >= CHART_H) {
        return;
    }
    uint8_t *px = buf->data + y * buf->header.stride + x * 4;
    uint32_t a = px[3], out = alpha + a * (255 - alpha) / 255;
    for (int c = 0; c < 3; c++) {
        uint32_t mixed = (255 * alpha + px[c] * a * (255 - alpha) / 255) / out;
        px[c] = (uint8_t)(mixed > 255 ? 255 : mixed); /* rounding can pass 255 */
    }
    px[3] = (uint8_t)out;
}

static void draw_chart(const typeof(shown.stocks[0]) *s)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(chart);
    memset(buf->data, 0, buf->header.stride * CHART_H);
    uint32_t colour = s->up ? GREEN : RED;
    uint8_t r = (colour >> 16) & 0xff, g = (colour >> 8) & 0xff, b = colour & 0xff;
    int32_t end = x_of(s->count - 1, s->count);

    /* The fill: under the line, strongest at the line, gone at the bottom; and the glow,
     * a soft band around the line, painted in the same pass (as segments its overlaps
     * left beads along the line). */
    for (int32_t x = 0; x <= end; x++) {
        float at = (float)x * (s->count - 1) / end;
        int i = (int)at;
        float f = at - i;
        uint16_t v = i + 1 < s->count ? (uint16_t)(s->points[i] * (1 - f) + s->points[i + 1] * f) : s->points[i];
        int32_t top = y_of(v);
        for (int32_t y = top - GLOW < 0 ? 0 : top - GLOW; y < CHART_H; y++) {
            int32_t fill = y >= top ? 100 * (CHART_H - y) / (CHART_H - top + 1) : 0;
            int32_t off = y > top ? y - top : top - y;
            int32_t glow = off < GLOW ? 90 * (GLOW - off) * (GLOW - off) / (GLOW * GLOW) : 0;
            uint8_t *px = buf->data + y * buf->header.stride + x * 4;
            px[0] = b, px[1] = g, px[2] = r, px[3] = (uint8_t)(fill > glow ? fill : glow);
        }
    }

    /* Each trading day after the first starts with a faint line, top to bottom, over the fill. */
    for (int d = 1; d < s->day_count; d++) {
        int32_t x = x_of(s->days[d].at, s->count);
        for (int32_t y = 12; y < CHART_H; y++) {
            lighten(buf, x, y, 30);
        }
    }

    /* The close before the week, dashed, across the whole chart. */
    int32_t base = y_of(s->base);
    for (int32_t x = 0; x < CHART_W; x++) {
        if (x % 14 < 8) {
            paint(buf, x, base, 0xc9c6d6, 150);
            paint(buf, x, base + 1, 0xc9c6d6, 150);
        }
    }

    lv_layer_t layer;
    lv_canvas_init_layer(chart, &layer);
    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.color = lv_color_hex(colour);
    line.round_start = line.round_end = 1;
    line.width = 4;
    for (int i = 1; i < s->count; i++) {
        line.p1.x = x_of(i - 1, s->count), line.p1.y = y_of(s->points[i - 1]);
        line.p2.x = x_of(i, s->count), line.p2.y = y_of(s->points[i]);
        lv_draw_line(&layer, &line);
    }
    lv_draw_rect_dsc_t mark;
    lv_draw_rect_dsc_init(&mark);
    mark.radius = LV_RADIUS_CIRCLE;
    mark.bg_color = lv_color_black();
    mark.border_color = lv_color_hex(0xf1eff7), mark.border_width = 3;
    int16_t marks[2] = {s->high_at, s->low_at};
    for (int m = 0; m < 2; m++) {
        if (marks[m] < 0 || marks[m] >= s->count - 2) {
            continue; /* at or next to the latest price, whose ripple marks the spot */
        }
        int32_t cx = x_of(marks[m], s->count), cy = y_of(s->points[marks[m]]);
        lv_area_t area = {.x1 = cx - 7, .y1 = cy - 7, .x2 = cx + 7, .y2 = cy + 7};
        lv_draw_rect(&layer, &mark, &area);
    }
    lv_canvas_finish_layer(chart, &layer);
    lv_obj_invalidate(chart);
}

/* "$190.10" over the high (or under the low), kept on the screen. */
static void place_mark(lv_obj_t *label, const char *words, int16_t at, const typeof(shown.stocks[0]) *s, bool over)
{
    lv_obj_set_flag(label, LV_OBJ_FLAG_HIDDEN, at < 0 || words[0] == '\0');
    if (at < 0) {
        return;
    }
    lv_label_set_text(label, words);
    lv_obj_update_layout(label);
    int32_t w = lv_obj_get_width(label);
    int32_t x = x_of(at, s->count) - w / 2;
    int32_t room = CHART_W - LEFT - w;
    int32_t y = y_of(s->points[at]) + (over ? -46 : 16);
    lv_obj_set_pos(label, x < LEFT ? LEFT : x > room ? room : x, y);
}

static void show_pill(lv_obj_t *pill, const char *words, bool up)
{
    lv_obj_set_flag(pill, LV_OBJ_FLAG_HIDDEN, words[0] == '\0');
    lv_obj_t *label = lv_obj_get_child(pill, 0);
    lv_label_set_text(label, words);
    uint32_t tone = up ? GREEN : RED;
    lv_obj_set_style_border_color(pill, lv_color_hex(tone), 0);
    lv_obj_set_style_text_color(label, lv_color_hex(tone), 0);
}

static void show(void)
{
    if (picked < 0 || picked >= shown.count) {
        return;
    }
    const typeof(shown.stocks[0]) *s = &shown.stocks[picked];
    snprintf(picked_ticker, sizeof picked_ticker, "%s", s->ticker);
    uint32_t colour = s->up ? GREEN : RED;

    lv_label_set_text(title, shown.title);
    show_pill(today, s->today, s->today_up);
    show_pill(gain, s->gain, s->gain_up);
    lv_label_set_text(ticker, s->ticker);
    lv_label_set_text(name, s->name);
    lv_label_set_text(week, s->week);
    lv_obj_set_style_text_color(week, lv_color_hex(colour), 0);
    lv_label_set_text(price, s->price);

    draw_chart(s);
    place_mark(high, s->high, s->high_at, s, true);
    place_mark(low, s->low, s->low_at, s, false);

    lv_obj_set_pos(pulse, x_of(s->count - 1, s->count) - RIPPLE / 2, y_of(s->points[s->count - 1]) - RIPPLE / 2);
    lv_obj_set_style_bg_color(dot, lv_color_hex(colour), 0);
    lv_obj_set_style_border_color(ripple, lv_color_hex(colour), 0);

    /* Each day's name under the middle of its stretch of the line. */
    for (int d = 0; d < DESK_STOCK_DAYS; d++) {
        lv_obj_set_flag(days[d], LV_OBJ_FLAG_HIDDEN, d >= s->day_count);
        if (d >= s->day_count) {
            continue;
        }
        int16_t from = s->days[d].at, to = d + 1 < s->day_count ? s->days[d + 1].at : s->count - 1;
        lv_label_set_text(days[d], s->days[d].label);
        lv_obj_update_layout(days[d]);
        int32_t mid = (x_of(from, s->count) + x_of(to, s->count)) / 2 - lv_obj_get_width(days[d]) / 2;
        lv_obj_set_pos(days[d], mid < 8 ? 8 : mid, DAYS_TOP);
    }

    /* Which of the holdings this is, as dots. */
    for (int i = 0; i < DESK_STOCKS; i++) {
        lv_obj_set_flag(dots[i], LV_OBJ_FLAG_HIDDEN, i >= shown.count || shown.count < 2);
        lv_obj_set_style_bg_color(dots[i], lv_color_hex(i == picked ? 0xf1eff7 : 0x3a3846), 0);
    }
}

/* Another holding than the last, each as likely as the others. */
static void pick(void)
{
    if (shown.count <= 1) {
        picked = shown.count - 1;
        return;
    }
    int next;
    do {
        next = (int)(esp_random() % (uint32_t)shown.count);
    } while (next == picked);
    picked = next;
}

/* The screen comes round (the light is still down): a new stock. */
static void on_load(lv_event_t *event)
{
    if (!shown.present) {
        return;
    }
    pick();
    show();
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_stock_version() == version) {
        return;
    }
    desk_stock_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    /* A new answer keeps the stock on show; it changes only when the screen comes round. */
    int same = -1;
    for (int i = 0; i < shown.count; i++) {
        if (strcmp(shown.stocks[i].ticker, picked_ticker) == 0) {
            same = i;
        }
    }
    if (same >= 0) {
        picked = same;
    } else {
        pick();
    }
    show();
}

/* The ripple grows from the latest price outwards and fades as it goes. */
static void grow(void *obj, int32_t at)
{
    int32_t size = DOT + (RIPPLE - DOT) * at / 1000;
    lv_obj_set_size(obj, size, size);
    lv_obj_set_style_border_opa(obj, (lv_opa_t)(170 * (1000 - at) / 1000), 0);
}

static lv_obj_t *make_pill(lv_obj_t *parent)
{
    lv_obj_t *pill = ui_plain(parent);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 4, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_border_width(pill, 2, 0);
    lv_obj_t *label = ui_text(pill, &instrument_24, GREEN);
    lv_obj_set_style_text_letter_space(label, 2, 0);
    lv_obj_add_flag(pill, LV_OBJ_FLAG_HIDDEN);
    return pill;
}

void screen_stock_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(VIOLET), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_one_line(screen, &instrument_24, GREY, 200);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    pills = ui_plain(screen);
    lv_obj_set_size(pills, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(pills, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(pills, 10, 0);
    lv_obj_align(pills, LV_ALIGN_TOP_RIGHT, -LEFT, 24);
    today = make_pill(pills);
    gain = make_pill(pills);

    ticker = ui_one_line(screen, &instrument_52_bold, 0xf1eff7, 340);
    lv_obj_set_pos(ticker, LEFT, 84);
    name = ui_one_line(screen, &instrument_24, GREY, 360);
    lv_obj_set_pos(name, LEFT, 152);
    week = ui_text(screen, &instrument_52_bold, GREEN);
    arrive_count(week);
    lv_obj_align(week, LV_ALIGN_TOP_RIGHT, -LEFT, 84);
    price = ui_text(screen, &instrument_24, 0xc9c6d6);
    lv_obj_align(price, LV_ALIGN_TOP_RIGHT, -LEFT, 152);

    chart = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(chart, lv_draw_buf_create(CHART_W, CHART_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(chart)->data, 0, lv_canvas_get_draw_buf(chart)->header.stride * CHART_H);
    lv_obj_set_pos(chart, 0, CHART_TOP);
    /* On the chart, so they appear as it draws in. */
    high = ui_text(chart, &instrument_24, 0xf1eff7);
    lv_obj_add_flag(high, LV_OBJ_FLAG_HIDDEN);
    low = ui_text(chart, &instrument_24, GREY);
    lv_obj_add_flag(low, LV_OBJ_FLAG_HIDDEN);
    pulse = ui_plain(chart);
    lv_obj_set_size(pulse, RIPPLE, RIPPLE);
    ripple = ui_plain(pulse);
    lv_obj_set_style_radius(ripple, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_border_width(ripple, 2, 0);
    lv_obj_align(ripple, LV_ALIGN_CENTER, 0, 0);
    dot = ui_plain(pulse);
    lv_obj_set_size(dot, DOT, DOT);
    lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(dot, lv_color_white(), 0);
    lv_obj_set_style_border_width(dot, 2, 0);
    lv_obj_align(dot, LV_ALIGN_CENTER, 0, 0);
    arrive_draw_in(chart, CHART_W, CHART_H);

    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, ripple);
    lv_anim_set_exec_cb(&anim, grow);
    lv_anim_set_values(&anim, 0, 1000);
    lv_anim_set_duration(&anim, 1800);
    lv_anim_set_repeat_delay(&anim, 600);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_out);
    lv_anim_start(&anim);

    for (int d = 0; d < DESK_STOCK_DAYS; d++) {
        days[d] = ui_text(screen, &instrument_24, GREY);
        lv_obj_add_flag(days[d], LV_OBJ_FLAG_HIDDEN);
    }

    lv_obj_t *row = ui_plain(screen);
    lv_obj_set_size(row, WIDTH, DOT);
    lv_obj_set_pos(row, LEFT, DOTS_TOP);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(row, 10, 0);
    for (int i = 0; i < DESK_STOCKS; i++) {
        dots[i] = ui_plain(row);
        lv_obj_set_size(dots[i], 8, 8);
        lv_obj_set_style_radius(dots[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(dots[i], LV_OPA_COVER, 0);
        lv_obj_add_flag(dots[i], LV_OBJ_FLAG_HIDDEN);
    }

    lv_obj_add_event_cb(screen, on_load, LV_EVENT_SCREEN_LOAD_START, NULL);
    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
