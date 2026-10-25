/* The ERROR takeover (plan.md M16, decided 2026-10-22): an open error covers the
 * panel, in a deep red with its title, its first lines and since when, until Dismiss
 * is tapped here or on another panel; the hub then stops sending it to all three until
 * the incident resolves. Also in quiet hours and with the lights off. Words from the
 * hub (app/desk_alerts.py).
 *
 * Lifted (plan.md M27): rings go out from behind the words, one after another: impossible
 * to miss, still calm. The red light is drawn once into a canvas: as a scaled image it
 * made every frame of the rings redraw it, at about 5 frames a second. */

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
#define RINGS 3
#define RING 140        /* a ring's size before it grows */
#define RING_MS 4200    /* one ring going out */
#define REACH 450       /* how big a ring grows: what it uncovers is redrawn every frame */
#define CENTRE_X (PAD + 30) /* where the rings start: behind the words' left edge */
#define CENTRE_Y 270

static lv_obj_t *layer, *rings[RINGS], *title, *body, *since, *button, *button_text;
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

/* 0 to 1000: grows to REACH round the same centre, fading. Its real size,
 * not a transform: a transformed object is drawn into a layer and scaled every frame. */
static void go_out(void *ring, int32_t at)
{
    int32_t size = RING + (REACH - RING) * at / 1000;
    lv_obj_set_size(ring, size, size);
    lv_obj_set_pos(ring, CENTRE_X - size / 2, CENTRE_Y - size / 2);
    lv_obj_set_style_border_opa(ring, (lv_opa_t)(110 - at * 110 / 1000), 0);
}

static void animate(void *var, lv_anim_exec_xcb_t exec, int32_t from, int32_t to, uint32_t ms, uint32_t delay)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, var);
    lv_anim_set_exec_cb(&anim, exec);
    lv_anim_set_values(&anim, from, to);
    lv_anim_set_duration(&anim, ms);
    lv_anim_set_delay(&anim, delay);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_out);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    lv_anim_start(&anim);
}

void takeover_start(void)
{
    layer = ui_plain(lv_layer_top());
    lv_obj_set_size(layer, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_opa(layer, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(layer, lv_color_hex(0x16080a), 0);
    lv_obj_add_flag(layer, LV_OBJ_FLAG_CLICKABLE); /* nothing reaches the screen under it */
    lv_obj_add_flag(layer, LV_OBJ_FLAG_HIDDEN);

    /* A deep red light from the top left, drawn once. */
    lv_obj_t *light = lv_canvas_create(layer);
    lv_canvas_set_draw_buf(light, lv_draw_buf_create(720, 720, LV_COLOR_FORMAT_RGB888, 0));
    lv_canvas_fill_bg(light, lv_color_hex(0x16080a), LV_OPA_COVER);
    lv_layer_t canvas_layer;
    lv_canvas_init_layer(light, &canvas_layer);
    lv_draw_image_dsc_t glow;
    lv_draw_image_dsc_init(&glow);
    glow.src = &glow_sky;
    glow.scale_x = glow.scale_y = 640;
    glow.pivot.x = glow.pivot.y = 0;
    glow.recolor = lv_color_hex(0xa0232c);
    glow.recolor_opa = LV_OPA_COVER;
    glow.opa = 140;
    lv_area_t area = {.x1 = -120, .y1 = 0, .x2 = -120 + glow_sky.header.w - 1, .y2 = glow_sky.header.h - 1};
    lv_draw_image(&canvas_layer, &glow, &area);
    lv_canvas_finish_layer(light, &canvas_layer);

    /* The rings, from behind the words' left edge, a third of a ring apart. */
    for (int i = 0; i < RINGS; i++) {
        rings[i] = ui_plain(layer);
        go_out(rings[i], 0);
        lv_obj_set_style_radius(rings[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(rings[i], 3, 0);
        lv_obj_set_style_border_color(rings[i], lv_color_hex(RED), 0);
        animate(rings[i], go_out, 0, 1000, RING_MS, i * RING_MS / RINGS);
    }

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
