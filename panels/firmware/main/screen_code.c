/* The House panel's Code screen (plan.md M20, chosen on 2026-10-21): your GitHub
 * contributions over 16 weeks as a grid, Monday at the top, in GitHub's quartiles
 * in violet, today outlined; under each column that week's total as a bar; then the
 * week so far, the streak and the busiest weekday, since M38 one row of hairline cells
 * with a figure each. Words and numbers from the hub (app/desk_code.py).
 *
 * The grid is painted into a canvas when the hub's answer changes: a hundred-odd
 * cells as LVGL shapes in one layer would stall its task queue. */

#include "screen_code.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "arrive.h"
#include "backdrops.h"
#include "ui.h"
#include "tokens.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define CELL 30
#define GAP 6
#define STEP (CELL + GAP)
#define GRID_WIDTH (16 * STEP - GAP)
#define GRID_HEIGHT (7 * STEP - GAP)
#define GRID_X (LEFT + (648 - GRID_WIDTH) / 2)
#define GRID_Y 136
#define BASE 544        /* the bars stand on this line */
#define BAR_HIGH 150
#define FACTS_TOP 592 /* the cells, under the city (or the bars), 36px off the bottom */
#define FACTS_H 92

/* GitHub's quartiles in the panels' violet, as on the hub's Code card. */
static const uint32_t LEVELS[5] = {0x17161d, 0x2b2655, 0x4a4191, 0x8074d5, TOK_DATA_LAVENDER};

static lv_obj_t *canvas, *title, *right, *months[6], *bars[16], *today_glow, *today_ring;
static lv_obj_t *facts[3], *figures[3], *units[3];
EXT_RAM_BSS_ATTR static desk_code_t shown; /* off the LVGL task's small stack */

/* One pixel of the grid canvas (ARGB8888, stored blue first). */
static void paint(lv_draw_buf_t *buf, int x, int y, uint32_t colour)
{
    uint8_t *px = buf->data + y * buf->header.stride + x * 4;
    px[0] = colour & 0xff, px[1] = (colour >> 8) & 0xff, px[2] = (colour >> 16) & 0xff, px[3] = 255;
}

/* A cell with rounded corners (radius 6), and today's with a white rim. */
static void cell(lv_draw_buf_t *buf, int x0, int y0, uint32_t colour, bool today)
{
    const int r = 6;
    for (int y = 0; y < CELL; y++) {
        for (int x = 0; x < CELL; x++) {
            int cx = x < r ? r - x : x >= CELL - r ? x - (CELL - r - 1) : 0;
            int cy = y < r ? r - y : y >= CELL - r ? y - (CELL - r - 1) : 0;
            int d2 = cx * cx + cy * cy;
            if (d2 > r * r) {
                continue;
            }
            bool rim = today && (x < 3 || y < 3 || x >= CELL - 3 || y >= CELL - 3 || d2 > (r - 3) * (r - 3));
            paint(buf, x0 + x, y0 + y, rim ? 0xffffff : colour);
        }
    }
}

/* The figure in the hub's words: what follows the last space ("this week 133": "133";
 * "busiest on Tuesdays": "Tue", a weekday cut to three letters). */
static const char *tail(const char *words)
{
    const char *space = strrchr(words, ' ');
    return space ? space + 1 : words;
}

/* A cell's figure and its small unit; the hub's words as they are when they do not fit. */
static void fact(int i, const char *figure, const char *unit)
{
    lv_label_set_text(figures[i], figure);
    lv_label_set_text(units[i], unit);
    lv_obj_set_flag(units[i], LV_OBJ_FLAG_HIDDEN, unit[0] == '\0');
}

static void show_facts(void)
{
    fact(0, tail(shown.this_week), "");
    int days = atoi(shown.streak); /* "9-day streak"; "" while there is none */
    char number[8];
    snprintf(number, sizeof number, "%d", days);
    fact(1, days > 1 ? number : "None", days > 1 ? "days" : "");
    const char *day = tail(shown.busiest);
    char short_day[4] = {0};
    if (strlen(day) > 3 && strstr(shown.busiest, "busiest on ") == shown.busiest) {
        memcpy(short_day, day, 3);
        day = short_day;
    }
    fact(2, day, "");
}

static void draw_grid(void)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    memset(buf->data, 0, buf->header.stride * GRID_HEIGHT);
    for (int i = 0; i < shown.day_count; i++) {
        int level = shown.levels[i] > 4 ? 4 : shown.levels[i];
        cell(buf, (i / 7) * STEP, (i % 7) * STEP, LEVELS[level], i == shown.day_count - 1);
    }
    lv_obj_invalidate(canvas);
}

/* 0 to 1000: the ring round today's block grows and fades (its real size, no transform). */
static void breathe(void *ring, int32_t at)
{
    int32_t size = 18 + 52 * at / 1000;
    lv_obj_set_size(ring, size, size);
    lv_obj_set_pos(ring, shown.city_x - size / 2, shown.city_y - size / 2);
    lv_obj_set_style_border_opa(ring, (lv_opa_t)(180 - at * 180 / 1000), 0);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_code_version() == version) {
        return;
    }
    shown = desk_code();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(title, shown.title);
    lv_label_set_text(right, shown.right);
    bool city = backdrops_painted(lv_obj_get_screen(canvas)); /* the bars and months step aside */
    for (int m = 0; m < 6; m++) {
        lv_obj_set_flag(months[m], LV_OBJ_FLAG_HIDDEN, city || m >= shown.month_count);
        if (m < shown.month_count) {
            lv_label_set_text(months[m], shown.months[m].name);
            lv_obj_set_pos(months[m], GRID_X + shown.months[m].week * STEP, GRID_Y - 40);
        }
    }
    for (int w = 0; w < 16; w++) {
        lv_obj_set_flag(bars[w], LV_OBJ_FLAG_HIDDEN, city || w >= shown.week_count);
        if (w >= shown.week_count) {
            continue;
        }
        int height = 8 + shown.weeks[w] * BAR_HIGH / 1000;
        bool last = w == shown.week_count - 1;
        lv_obj_set_size(bars[w], CELL, height);
        lv_obj_set_pos(bars[w], GRID_X + w * STEP, BASE - height);
        lv_obj_set_style_bg_color(bars[w], lv_color_hex(last ? TOK_DATA_LAVENDER : TOK_ACCENT_LINE), 0);
        lv_obj_set_style_bg_opa(bars[w], last ? LV_OPA_COVER : 90 + 165 * shown.weeks[w] / 1000, 0);
    }
    lv_obj_set_pos(today_glow, shown.city_x - 9, shown.city_y - 9);
    show_facts();
    draw_grid();
}

void screen_code_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* House's quiet violet from the top. */
    lv_obj_t *sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(TOK_VIOLET), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, TOK_DESK_MUTED);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    right = ui_text(screen, &instrument_24, TOK_DESK_MUTED);
    lv_obj_set_style_text_letter_space(right, 2, 0);
    lv_obj_align(right, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    for (int m = 0; m < 6; m++) {
        months[m] = ui_text(screen, &instrument_24, TOK_DESK_FAINT);
    }
    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(GRID_WIDTH, GRID_HEIGHT, LV_COLOR_FORMAT_ARGB8888, 0));
    lv_obj_set_pos(canvas, GRID_X, GRID_Y);
    arrive_draw_in(canvas, GRID_WIDTH, GRID_HEIGHT);
    memset(lv_canvas_get_draw_buf(canvas)->data, 0, lv_canvas_get_draw_buf(canvas)->header.stride * GRID_HEIGHT);

    for (int w = 0; w < 16; w++) {
        bars[w] = ui_plain(screen);
        lv_obj_set_style_radius(bars[w], 6, 0);
        lv_obj_add_flag(bars[w], LV_OBJ_FLAG_HIDDEN);
    }
    lv_obj_t *base = ui_plain(screen);
    lv_obj_set_size(base, 648, 2);
    lv_obj_set_pos(base, LEFT, BASE + 3);
    lv_obj_set_style_bg_color(base, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(base, 25, 0);

    lv_obj_t *per_week = ui_text(screen, &instrument_24, TOK_DESK_MUTED);
    lv_label_set_text(per_week, "per week");
    lv_obj_set_pos(per_week, LEFT, BASE + 16);

    /* Painted (plan.md M27): the hub draws the weeks as a city; the grid, the months and the
     * bars step aside, and today's block breathes. */
    backdrops_aside(canvas);
    backdrops_aside(base);
    backdrops_aside(per_week);
    for (int m = 0; m < 6; m++) {
        backdrops_aside(months[m]);
    }
    for (int w = 0; w < 16; w++) {
        backdrops_aside(bars[w]);
    }
    today_ring = ui_plain(screen);
    lv_obj_set_style_radius(today_ring, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_border_width(today_ring, 2, 0);
    lv_obj_set_style_border_color(today_ring, lv_color_white(), 0);
    backdrops_with(today_ring);
    today_glow = ui_plain(screen);
    lv_obj_set_size(today_glow, 18, 18);
    lv_obj_set_style_radius(today_glow, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(today_glow, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(today_glow, 60, 0);
    lv_obj_set_style_shadow_width(today_glow, 24, 0);
    lv_obj_set_style_shadow_color(today_glow, lv_color_hex(0xd8d0ff), 0);
    lv_obj_set_style_shadow_opa(today_glow, 200, 0);
    backdrops_with(today_glow);
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, today_ring);
    lv_anim_set_exec_cb(&anim, breathe);
    lv_anim_set_values(&anim, 0, 1000);
    lv_anim_set_duration(&anim, 2200);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_out);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    lv_anim_start(&anim);
    /* This week, the streak and the busiest day: a cell each, its name over its figure. */
    static const char *const NAMES[3] = {"THIS WEEK", "STREAK", "BUSIEST"};
    ui_cells(screen, LEFT, FACTS_TOP, 648, FACTS_H, 3, facts);
    for (int i = 0; i < 3; i++) {
        lv_obj_t *name = ui_text(facts[i], &instrument_24, TOK_DESK_MUTED);
        lv_obj_set_style_text_letter_space(name, 2, 0);
        lv_label_set_text(name, NAMES[i]);
        lv_obj_set_pos(name, 18, 10);
        lv_obj_t *figure = ui_plain(facts[i]);
        lv_obj_set_size(figure, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
        lv_obj_set_flex_flow(figure, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(figure, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_END);
        lv_obj_set_style_pad_column(figure, 6, 0);
        lv_obj_set_pos(figure, 18, 38);
        figures[i] = ui_text(figure, &instrument_40, TOK_DESK_FG);
        units[i] = ui_text(figure, &instrument_24, TOK_DESK_MUTED);
        lv_obj_set_style_pad_bottom(units[i], 5, 0);
    }

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
