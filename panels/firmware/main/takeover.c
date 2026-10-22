/* The ERROR takeover (plan.md M16, decided 2026-10-22): an open error covers the
 * panel, in a deep red with its title, its first lines and since when, until Dismiss
 * is tapped here or on another panel; the hub then stops sending it to all three until
 * the incident resolves. Also in quiet hours and with the lights off. Words from the
 * hub (app/desk_alerts.py). */

#include "takeover.h"

#include <stdio.h>
#include <string.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define PAD 56
#define WIDTH (720 - 2 * PAD)
#define RED 0xff6b6b

static lv_obj_t *layer, *title, *body, *since, *button, *button_text;
static char dismissed[96]; /* tapped here: hidden until the hub's next answer says more */
EXT_RAM_BSS_ATTR static desk_takeover_t shown;

bool takeover_showing(void)
{
    return layer && !lv_obj_has_flag(layer, LV_OBJ_FLAG_HIDDEN);
}

static void on_dismiss(lv_event_t *event)
{
    if (!shown.present || !actions_dismiss(shown.key)) {
        return;
    }
    snprintf(dismissed, sizeof dismissed, "%s", shown.key);
    lv_obj_add_flag(layer, LV_OBJ_FLAG_HIDDEN);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_takeover_version() == version) {
        return;
    }
    desk_takeover_copy(&shown);
    version = shown.version;
    /* A dismissed error comes back only when it failed to reach the hub (it still
     * sends the same one after a moment) or a new one opens. */
    static int answers_since_dismiss;
    bool same = shown.present && strcmp(shown.key, dismissed) == 0;
    answers_since_dismiss = same ? answers_since_dismiss + 1 : 0;
    if (!same) {
        dismissed[0] = '\0';
    }
    bool show = shown.present && (!same || answers_since_dismiss > 2);
    if (show) {
        lv_label_set_text(title, shown.title);
        lv_label_set_text(body, shown.body);
        char line[48];
        snprintf(line, sizeof line, "Open since %s", shown.since);
        lv_label_set_text(since, line);
    }
    lv_obj_set_flag(layer, LV_OBJ_FLAG_HIDDEN, !show);
}

void takeover_start(void)
{
    layer = ui_plain(lv_layer_top());
    lv_obj_set_size(layer, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(layer, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(layer, lv_color_hex(0x16080a), 0);
    lv_obj_add_flag(layer, LV_OBJ_FLAG_CLICKABLE); /* nothing reaches the screen under it */
    lv_obj_add_flag(layer, LV_OBJ_FLAG_HIDDEN);

    /* A deep red light from the top left. */
    lv_obj_t *sky = lv_image_create(layer);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 640);
    lv_obj_set_pos(sky, -120, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0xa0232c), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 140, 0);

    lv_obj_t *words = ui_plain(layer);
    lv_obj_set_size(words, WIDTH, LV_SIZE_CONTENT);
    lv_obj_align(words, LV_ALIGN_LEFT_MID, PAD, 0);
    lv_obj_set_flex_flow(words, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(words, 18, 0);

    lv_obj_t *word = ui_text(words, &instrument_24, RED);
    lv_obj_set_style_text_letter_space(word, 4, 0);
    lv_label_set_text(word, "ERROR");
    title = ui_text(words, &instrument_52_bold, 0xffffff);
    lv_label_set_long_mode(title, LV_LABEL_LONG_DOT);
    lv_obj_set_width(title, WIDTH);
    lv_obj_set_style_max_height(title, 3 * lv_font_get_line_height(&instrument_52_bold), 0);
    body = ui_text(words, &instrument_24, 0xe2c3c5);
    lv_label_set_long_mode(body, LV_LABEL_LONG_DOT);
    lv_obj_set_width(body, WIDTH);
    lv_obj_set_style_max_height(body, 4 * lv_font_get_line_height(&instrument_24), 0);
    since = ui_one_line(words, &instrument_24, 0xb88a8d, WIDTH);

    button = ui_plain(words);
    lv_obj_set_size(button, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(button, 40, 0);
    lv_obj_set_style_pad_ver(button, 16, 0);
    lv_obj_set_style_margin_top(button, 18, 0);
    lv_obj_set_style_radius(button, 40, 0);
    lv_obj_set_style_bg_opa(button, 40, 0);
    lv_obj_set_style_bg_color(button, lv_color_hex(RED), 0);
    lv_obj_set_style_border_width(button, 2, 0);
    lv_obj_set_style_border_color(button, lv_color_hex(RED), 0);
    lv_obj_add_flag(button, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_ext_click_area(button, 16);
    lv_obj_add_event_cb(button, on_dismiss, LV_EVENT_CLICKED, NULL);
    button_text = ui_text(button, &instrument_28_bold, 0xffffff);
    lv_label_set_text(button_text, "Dismiss");

    lv_timer_create(tick, 500, NULL);
}
