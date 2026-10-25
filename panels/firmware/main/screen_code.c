/* The House panel's Code screen (plan.md M20, chosen on 2026-10-21): your GitHub
 * contributions over 16 weeks as a grid, Monday at the top, in GitHub's quartiles
 * in violet, today outlined; under each column that week's total as a bar; then the
 * week so far, the streak and the busiest weekday. Words and numbers from the hub
 * (app/desk_code.py).
 *
 * The grid is painted into a canvas when the hub's answer changes: a hundred-odd
 * cells as LVGL shapes in one layer would stall its task queue. */

#include "screen_code.h"

#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "arrive.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
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
#define BASE 560        /* the bars stand on this line */
#define BAR_HIGH 150

/* GitHub's quartiles in the panels' violet, as on the hub's Code card. */
static const uint32_t LEVELS[5] = {0x17161d, 0x2b2655, 0x4a4191, 0x8074d5, 0xc3b9ff};

static lv_obj_t *canvas, *title, *right, *months[6], *bars[16], *this_week, *streak, *busiest;
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
    for (int m = 0; m < 6; m++) {
        lv_obj_set_flag(months[m], LV_OBJ_FLAG_HIDDEN, m >= shown.month_count);
        if (m < shown.month_count) {
            lv_label_set_text(months[m], shown.months[m].name);
            lv_obj_set_pos(months[m], GRID_X + shown.months[m].week * STEP, GRID_Y - 40);
        }
    }
    for (int w = 0; w < 16; w++) {
        lv_obj_set_flag(bars[w], LV_OBJ_FLAG_HIDDEN, w >= shown.week_count);
        if (w >= shown.week_count) {
            continue;
        }
        int height = 8 + shown.weeks[w] * BAR_HIGH / 1000;
        bool last = w == shown.week_count - 1;
        lv_obj_set_size(bars[w], CELL, height);
        lv_obj_set_pos(bars[w], GRID_X + w * STEP, BASE - height);
        lv_obj_set_style_bg_color(bars[w], lv_color_hex(last ? 0xc3b9ff : 0x8f80ff), 0);
        lv_obj_set_style_bg_opa(bars[w], last ? LV_OPA_COVER : 90 + 165 * shown.weeks[w] / 1000, 0);
    }
    lv_label_set_text(this_week, shown.this_week);
    lv_label_set_text(streak, shown.streak);
    lv_label_set_text(busiest, shown.busiest);
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
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    right = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(right, 2, 0);
    lv_obj_align(right, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    for (int m = 0; m < 6; m++) {
        months[m] = ui_text(screen, &instrument_24, 0x6c6a78);
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

    lv_obj_t *per_week = ui_text(screen, &instrument_24, 0x8a8794);
    lv_label_set_text(per_week, "per week");
    lv_obj_set_pos(per_week, LEFT, BASE + 16);
    this_week = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_align(this_week, LV_ALIGN_TOP_RIGHT, -LEFT, BASE + 16);
    streak = ui_text(screen, &instrument_28_bold, 0xffffff);
    lv_obj_set_pos(streak, LEFT, 640);
    busiest = ui_text(screen, &instrument_24, 0xa7a7b4);
    lv_obj_align(busiest, LV_ALIGN_TOP_RIGHT, -LEFT, 644);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
