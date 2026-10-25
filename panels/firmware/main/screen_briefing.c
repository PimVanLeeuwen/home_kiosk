/* The Now panel's Briefing screen (plan.md M26, the mockup in docs/hub-ai-mockup.html):
 * the morning digest Claude wrote at 06:30, as one line in large type and four facts
 * as quiet rows, each with a violet dot, until 09:00. Words from the hub
 * (app/desk_briefing.py); the panel only places them.
 *
 * Long text is cut with "..." at a fixed height (LV_LABEL_LONG_DOT needs one). */

#include "screen_briefing.h"

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define LINE_TOP 92
#define LINE_ROWS 3
#define FACTS_TOP 300
#define FACT_HEIGHT 76
#define FACT_GAP 12

static lv_obj_t *title, *line, *rows[4], *facts[4], *as_of;
EXT_RAM_BSS_ATTR static desk_briefing_t shown; /* off the LVGL task's small stack */

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_briefing_version() == version) {
        return;
    }
    shown = desk_briefing();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(title, shown.title);
    lv_label_set_text(line, shown.line);
    for (int i = 0; i < 4; i++) {
        lv_obj_set_flag(rows[i], LV_OBJ_FLAG_HIDDEN, i >= shown.fact_count);
        lv_label_set_text(facts[i], i < shown.fact_count ? shown.facts[i] : "");
    }
    lv_label_set_text(as_of, shown.as_of);
}

void screen_briefing_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* The morning's violet from the top, a little warmer than House's. */
    lv_obj_t *sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x8f7cf6), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 80, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);

    line = ui_text(screen, &instrument_40, 0xffffff);
    lv_label_set_long_mode(line, LV_LABEL_LONG_DOT);
    lv_obj_set_size(line, WIDTH, LINE_ROWS * lv_font_get_line_height(&instrument_40));
    lv_obj_set_pos(line, LEFT, LINE_TOP);

    for (int i = 0; i < 4; i++) {
        rows[i] = ui_plain(screen);
        lv_obj_set_size(rows[i], WIDTH, FACT_HEIGHT);
        lv_obj_set_pos(rows[i], LEFT, FACTS_TOP + i * (FACT_HEIGHT + FACT_GAP));
        lv_obj_set_style_radius(rows[i], 18, 0);
        lv_obj_set_style_bg_color(rows[i], lv_color_hex(0x15141c), 0);
        lv_obj_set_style_bg_opa(rows[i], LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(rows[i], lv_color_hex(0x26232f), 0);
        lv_obj_set_style_border_width(rows[i], 1, 0);
        lv_obj_add_flag(rows[i], LV_OBJ_FLAG_HIDDEN);

        lv_obj_t *dot = ui_plain(rows[i]);
        lv_obj_set_size(dot, 12, 12);
        lv_obj_align(dot, LV_ALIGN_LEFT_MID, 26, 0);
        lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(dot, lv_color_hex(0x9d8cff), 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
        lv_obj_set_style_shadow_color(dot, lv_color_hex(0x9d8cff), 0);
        lv_obj_set_style_shadow_width(dot, 12, 0);
        lv_obj_set_style_shadow_opa(dot, 140, 0);

        facts[i] = ui_one_line(rows[i], &instrument_28_bold, 0xf2f1f6, WIDTH - 90);
        lv_obj_align(facts[i], LV_ALIGN_LEFT_MID, 58, 0);
    }

    as_of = ui_text(screen, &instrument_24, 0x6c6a78);
    lv_obj_set_pos(as_of, LEFT, 664);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
