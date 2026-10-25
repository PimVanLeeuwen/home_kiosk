/* The House panel's pipelines card while nothing runs (plan.md M21), as in the
 * mockup: each watched repo with a dot and a line for its last result, and its
 * last ten runs on main as bars, as tall as they took (capped by the hub), red
 * for a failed run. Wording and colours from the hub (app/desk_pipelines.py). */

#include "screen_pipelines.h"

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define ROW_TOP 150
#define ROW_STEP 160
#define BARS_LEFT 444
#define BAR_WIDTH 16
#define BAR_GAP 8
#define BAR_LOW 8      /* the shortest bar */
#define BAR_HIGH 70    /* added for the longest run */
#define BAR_BOTTOM 78  /* below a row's top */

static struct {
    lv_obj_t *row, *dot, *name, *line, *bars[10];
} rows[3];
EXT_RAM_BSS_ATTR static desk_pipelines_t shown; /* off the LVGL task's small stack */

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_pipelines_version() == version) {
        return;
    }
    desk_pipelines_copy(&shown);
    version = shown.version;
    for (int i = 0; i < 3; i++) {
        lv_obj_set_flag(rows[i].row, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i >= shown.count) {
            continue;
        }
        typeof(shown.repos[0]) *r = &shown.repos[i];
        lv_obj_set_style_bg_color(rows[i].dot, lv_color_hex(r->colour), 0);
        lv_label_set_text(rows[i].name, r->name);
        lv_label_set_text(rows[i].line, r->line);
        for (int b = 0; b < 10; b++) {
            lv_obj_t *bar = rows[i].bars[b];
            lv_obj_set_flag(bar, LV_OBJ_FLAG_HIDDEN, b >= r->bar_count);
            if (b >= r->bar_count) {
                continue;
            }
            int height = BAR_LOW + r->bars[b].height * BAR_HIGH / 1000;
            lv_obj_set_size(bar, BAR_WIDTH, height);
            lv_obj_set_pos(bar, BARS_LEFT + b * (BAR_WIDTH + BAR_GAP), BAR_BOTTOM - height);
            lv_obj_set_style_bg_color(bar, lv_color_hex(r->bars[b].ok ? 0x8f80ff : 0xe5646a), 0);
            lv_obj_set_style_bg_opa(bar, b == r->bar_count - 1 ? LV_OPA_COVER : 140, 0);
        }
    }
}

void screen_pipelines_create(lv_obj_t *screen)
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

    lv_obj_t *title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_label_set_text(title, "PIPELINES");
    lv_obj_set_pos(title, LEFT, 30);
    lv_obj_t *right = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(right, 2, 0);
    lv_label_set_text(right, "LAST 10 RUNS ON MAIN");
    lv_obj_align(right, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    for (int i = 0; i < 3; i++) {
        lv_obj_t *row = rows[i].row = ui_plain(screen);
        lv_obj_set_size(row, 720, 120);
        lv_obj_set_pos(row, 0, ROW_TOP + i * ROW_STEP);
        rows[i].dot = ui_plain(row);
        lv_obj_set_size(rows[i].dot, 20, 20);
        lv_obj_set_pos(rows[i].dot, LEFT + 4, 10);
        lv_obj_set_style_radius(rows[i].dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(rows[i].dot, LV_OPA_COVER, 0);
        rows[i].name = ui_text(row, &instrument_28_bold, 0xffffff);
        lv_obj_set_pos(rows[i].name, LEFT + 40, 0);
        rows[i].line = ui_text(row, &instrument_24, 0x8a8794);
        lv_obj_set_pos(rows[i].line, LEFT + 40, 44);
        for (int b = 0; b < 10; b++) {
            lv_obj_t *bar = rows[i].bars[b] = ui_plain(row);
            lv_obj_set_style_radius(bar, 4, 0);
        }
    }

    lv_obj_t *note = ui_text(screen, &instrument_24, 0x8a8794);
    lv_label_set_text(note, "Bar height is run time; red is a failed run");
    lv_obj_set_pos(note, LEFT, 664);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
