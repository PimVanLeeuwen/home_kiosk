/* The Home panel's lights (plan.md M17), as in the desk panels mockup: the
 * living room's groups as tiles lit in the white they have, a row of whites for
 * the group that has a choice, and one switch for the whole room.
 *
 * A tap on a tile switches its group; holding it opens a sheet with a slider
 * for its brightness; a tap on a white sets it. Every change goes to the hub
 * from actions.c (with the board's key) and shows at once; the hub's answer
 * then shows what the bridge really did.
 *
 * Lifted (plan.md M27): each lit group throws a pool of its own light behind its tile,
 * larger the brighter it is, and the tiles are glass over it. Drawn here, not by the hub,
 * so a tap changes the light at once. */

#include "screen_lights.h"

#include <stdio.h>
#include <string.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define WIDTH 648
#define TILE_TOP 84
#define TILE_GAP 12
#define TILE_HEIGHT 300
#define WHITE 60

static lv_obj_t *title, *count, *whites_label, *whites_row, *room_button, *room_label;
static struct {
    lv_obj_t *tile, *glow, *pool, *name, *line, *dot;
} tiles[DESK_LIGHT_GROUPS];
static lv_obj_t *whites[DESK_WHITES];
static lv_obj_t *sheet, *sheet_name, *sheet_value, *slider;
static int sheet_group = -1;
static bool held; /* a long press opened the sheet: the release is no tap */
EXT_RAM_BSS_ATTR static desk_lights_t shown; /* off the LVGL task's small stack */

/* How a tile looks: lit in its white with a glow, or dark and quiet. */
static void paint_tile(int i)
{
    bool on = shown.groups[i].on;
    uint32_t tone = shown.groups[i].tone;
    lv_obj_set_style_bg_color(tiles[i].tile, lv_color_hex(on ? 0x221f1c : 0x141318), 0);
    lv_obj_set_style_bg_opa(tiles[i].tile, on ? 150 : LV_OPA_COVER, 0); /* glass while lit */
    int bright = shown.groups[i].brightness < 1 ? 1 : shown.groups[i].brightness;
    lv_image_set_scale(tiles[i].pool, 256 * 2 + 256 * 2 * bright / 100);
    lv_obj_set_style_image_recolor(tiles[i].pool, lv_color_hex(tone), 0);
    lv_obj_set_style_image_opa(tiles[i].pool, (lv_opa_t)(90 + bright * 110 / 100), 0);
    lv_obj_set_flag(tiles[i].pool, LV_OBJ_FLAG_HIDDEN, !on || lv_obj_has_flag(tiles[i].tile, LV_OBJ_FLAG_HIDDEN));
    lv_obj_set_style_border_color(tiles[i].tile, lv_color_hex(on ? tone : 0xffffff), 0);
    lv_obj_set_style_border_opa(tiles[i].tile, on ? 110 : 30, 0);
    lv_obj_set_style_image_recolor(tiles[i].glow, lv_color_hex(tone), 0);
    lv_obj_set_flag(tiles[i].glow, LV_OBJ_FLAG_HIDDEN, !on);
    lv_obj_set_style_text_color(tiles[i].name, lv_color_hex(on ? 0xffffff : 0x8a8794), 0);
    lv_obj_set_style_bg_color(tiles[i].dot, lv_color_hex(on ? tone : 0x3a3844), 0);
    lv_label_set_text(tiles[i].name, shown.groups[i].name);
    lv_label_set_text(tiles[i].line, shown.groups[i].line);
}

static void paint_whites(void)
{
    /* A definite width: sized to its content, the row kept the size it had
     * while its whites were hidden. */
    int n = shown.has_whites ? shown.choice_count : 0;
    lv_obj_set_width(whites_row, n ? n * WHITE + (n - 1) * 14 + 16 : 0);
    lv_obj_set_pos(whites_row, LEFT - 8, TILE_TOP + TILE_HEIGHT + 68); /* under its label */
    for (int i = 0; i < DESK_WHITES; i++) {
        bool there = shown.has_whites && i < shown.choice_count;
        lv_obj_set_flag(whites[i], LV_OBJ_FLAG_HIDDEN, !there);
        if (!there) {
            continue;
        }
        bool chosen = shown.choices[i].kelvin == shown.whites_kelvin;
        lv_obj_set_style_bg_color(whites[i], lv_color_hex(shown.choices[i].tone), 0);
        lv_obj_set_style_border_width(whites[i], chosen ? 4 : 0, 0);
        lv_obj_set_style_shadow_width(whites[i], chosen ? 24 : 0, 0);
        lv_obj_set_style_shadow_color(whites[i], lv_color_hex(shown.choices[i].tone), 0);
    }
}

static void paint(void)
{
    char caps[48];
    ui_upper(caps, sizeof caps, shown.title);
    lv_label_set_text(title, caps);
    ui_upper(caps, sizeof caps, shown.count);
    lv_label_set_text(count, caps);
    for (int i = 0; i < DESK_LIGHT_GROUPS; i++) {
        lv_obj_set_flag(tiles[i].tile, LV_OBJ_FLAG_HIDDEN, i >= shown.group_count);
        lv_obj_add_flag(tiles[i].pool, LV_OBJ_FLAG_HIDDEN); /* paint_tile lights it again */
        if (i < shown.group_count) {
            paint_tile(i);
        }
    }
    lv_obj_set_flag(whites_label, LV_OBJ_FLAG_HIDDEN, !shown.has_whites);
    if (shown.has_whites) {
        char line[48];
        snprintf(line, sizeof line, "%s white", shown.whites_name);
        ui_upper(caps, sizeof caps, line);
        lv_label_set_text(whites_label, caps);
    }
    paint_whites();
    lv_label_set_text(room_label, shown.any_on ? "Switch all off" : "Switch all on");
}

/* --- taps --------------------------------------------------------------------------- */

static void on_tile(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    if (held) {
        held = false;
        return;
    }
    if (i >= shown.group_count) {
        return;
    }
    bool on = !shown.groups[i].on;
    if (actions_lights(shown.groups[i].id, on ? "{\"on\":true}" : "{\"on\":false}")) {
        shown.groups[i].on = on; /* at once; the hub's answer follows */
        paint_tile(i);
    }
}

static void on_white(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    char body[32];
    snprintf(body, sizeof body, "{\"kelvin\":%d}", shown.choices[i].kelvin);
    if (actions_lights(shown.whites_group, body)) {
        shown.whites_kelvin = shown.choices[i].kelvin;
        paint_whites();
    }
}

static void on_room(lv_event_t *event)
{
    if (actions_lights("room", shown.any_on ? "{\"on\":false}" : "{\"on\":true}")) {
        shown.any_on = !shown.any_on;
        lv_label_set_text(room_label, shown.any_on ? "Switch all off" : "Switch all on");
    }
}

/* --- the brightness sheet ----------------------------------------------------------- */

static void close_sheet(void)
{
    sheet_group = -1;
    lv_obj_add_flag(sheet, LV_OBJ_FLAG_HIDDEN);
}

static void on_hold(lv_event_t *event)
{
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    if (i >= shown.group_count) {
        return;
    }
    held = true;
    sheet_group = i;
    lv_label_set_text(sheet_name, shown.groups[i].name);
    int value = shown.groups[i].on ? shown.groups[i].brightness : 0;
    lv_slider_set_value(slider, value < 1 ? 1 : value, LV_ANIM_OFF);
    lv_label_set_text_fmt(sheet_value, "%d%%", value);
    lv_obj_set_style_bg_color(slider, lv_color_hex(shown.groups[i].tone), LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(slider, lv_color_hex(shown.groups[i].tone), LV_PART_KNOB);
    lv_obj_remove_flag(sheet, LV_OBJ_FLAG_HIDDEN);
}

static void on_slide(lv_event_t *event)
{
    lv_label_set_text_fmt(sheet_value, "%d%%", (int)lv_slider_get_value(slider));
}

static void on_slide_done(lv_event_t *event)
{
    if (sheet_group < 0) {
        return;
    }
    char body[32];
    int value = (int)lv_slider_get_value(slider);
    snprintf(body, sizeof body, "{\"brightness\":%d}", value);
    if (actions_lights(shown.groups[sheet_group].id, body)) {
        shown.groups[sheet_group].on = true;
        shown.groups[sheet_group].brightness = value;
        paint_tile(sheet_group);
    }
}

static void on_backdrop(lv_event_t *event)
{
    if (lv_event_get_target(event) == sheet) {
        close_sheet(); /* a tap beside the card closes it */
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_lights_version() == version || sheet_group >= 0) {
        return; /* not while the sheet is open: it would jump under the finger */
    }
    shown = desk_lights();
    version = shown.version;
    if (shown.present) {
        paint();
    }
}

void screen_lights_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 24);
    count = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(count, 2, 0);
    lv_obj_align(count, LV_ALIGN_TOP_RIGHT, -LEFT, 24);

    /* Up to four tiles, two side by side. */
    int tile_width = (WIDTH - TILE_GAP) / 2;
    for (int i = 0; i < DESK_LIGHT_GROUPS; i++) {
        /* The pool of light, under every tile (made first, so it lies under them). */
        int x = LEFT + (i % 2) * (tile_width + TILE_GAP) + tile_width / 2;
        int y = TILE_TOP + (i / 2) * (TILE_HEIGHT + TILE_GAP) + (i < 2 ? TILE_HEIGHT : TILE_HEIGHT / 2) / 2;
        tiles[i].pool = lv_image_create(screen);
        lv_image_set_src(tiles[i].pool, &glow_round);
        lv_image_set_pivot(tiles[i].pool, 80, 80);
        lv_obj_set_pos(tiles[i].pool, x - 80, y - 80);
        lv_obj_set_style_image_recolor_opa(tiles[i].pool, LV_OPA_COVER, 0);
        lv_obj_remove_flag(tiles[i].pool, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_flag(tiles[i].pool, LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < DESK_LIGHT_GROUPS; i++) {
        lv_obj_t *tile = tiles[i].tile = ui_plain(screen);
        lv_obj_set_size(tile, tile_width, i < 2 ? TILE_HEIGHT : TILE_HEIGHT / 2);
        lv_obj_set_pos(tile, LEFT + (i % 2) * (tile_width + TILE_GAP),
                       TILE_TOP + (i / 2) * (TILE_HEIGHT + TILE_GAP));
        lv_obj_set_style_radius(tile, 28, 0);
        lv_obj_set_style_clip_corner(tile, true, 0);
        lv_obj_set_style_bg_opa(tile, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(tile, 2, 0);
        lv_obj_add_flag(tile, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_add_event_cb(tile, on_tile, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        lv_obj_add_event_cb(tile, on_hold, LV_EVENT_LONG_PRESSED, (void *)(intptr_t)i);

        tiles[i].glow = lv_image_create(tile);
        lv_image_set_src(tiles[i].glow, &glow_round);
        lv_image_set_scale(tiles[i].glow, 256 * 3);
        lv_obj_set_pos(tiles[i].glow, 0, -60);
        lv_obj_set_style_image_recolor_opa(tiles[i].glow, LV_OPA_COVER, 0);
        lv_obj_set_style_image_opa(tiles[i].glow, 110, 0);

        tiles[i].name = ui_text(tile, &instrument_40, 0xffffff);
        lv_label_set_long_mode(tiles[i].name, LV_LABEL_LONG_WRAP);
        lv_obj_set_width(tiles[i].name, tile_width - 72);
        lv_obj_set_pos(tiles[i].name, 26, 22);
        tiles[i].line = ui_text(tile, &instrument_24, 0xd6d3df);
        lv_obj_align(tiles[i].line, LV_ALIGN_BOTTOM_LEFT, 26, -24);
        tiles[i].dot = ui_plain(tile);
        lv_obj_set_size(tiles[i].dot, 18, 18);
        lv_obj_set_style_radius(tiles[i].dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(tiles[i].dot, LV_OPA_COVER, 0);
        lv_obj_align(tiles[i].dot, LV_ALIGN_TOP_RIGHT, -24, 32);
        lv_obj_add_flag(tile, LV_OBJ_FLAG_HIDDEN);
    }

    /* The row of whites, warm to cool. */
    int row_top = TILE_TOP + TILE_HEIGHT + 28;
    whites_label = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(whites_label, 2, 0);
    lv_obj_set_pos(whites_label, LEFT, row_top);
    whites_row = ui_plain(screen);
    lv_obj_set_size(whites_row, 0, WHITE + 16);
    lv_obj_set_flex_flow(whites_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(whites_row, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(whites_row, 14, 0);
    lv_obj_set_style_pad_all(whites_row, 8, 0);
    for (int i = 0; i < DESK_WHITES; i++) {
        lv_obj_t *white = whites[i] = ui_plain(whites_row);
        lv_obj_set_size(white, WHITE, WHITE);
        lv_obj_set_style_radius(white, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(white, LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(white, lv_color_white(), 0);
        lv_obj_set_style_shadow_opa(white, 140, 0);
        lv_obj_add_flag(white, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_set_ext_click_area(white, 6);
        lv_obj_add_event_cb(white, on_white, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        lv_obj_add_flag(white, LV_OBJ_FLAG_HIDDEN);
    }

    /* The whole room at once. */
    room_button = ui_plain(screen);
    lv_obj_set_size(room_button, WIDTH, 96);
    lv_obj_align(room_button, LV_ALIGN_BOTTOM_MID, 0, -48);
    lv_obj_set_style_radius(room_button, 48, 0);
    lv_obj_set_style_bg_opa(room_button, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(room_button, lv_color_hex(0x1a1920), 0);
    lv_obj_set_style_border_width(room_button, 2, 0);
    lv_obj_set_style_border_color(room_button, lv_color_white(), 0);
    lv_obj_set_style_border_opa(room_button, 30, 0);
    lv_obj_add_flag(room_button, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(room_button, on_room, LV_EVENT_CLICKED, NULL);
    room_label = ui_text(room_button, &instrument_28_bold, 0xf1eff7);
    lv_obj_center(room_label);

    /* The brightness sheet: a card over a dark veil, opened by holding a tile. */
    sheet = lv_obj_create(screen);
    lv_obj_remove_style_all(sheet);
    lv_obj_set_size(sheet, 720, 720);
    lv_obj_set_style_bg_opa(sheet, 190, 0);
    lv_obj_set_style_bg_color(sheet, lv_color_black(), 0);
    lv_obj_add_flag(sheet, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(sheet, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(sheet, on_backdrop, LV_EVENT_CLICKED, NULL);
    lv_obj_t *card = ui_plain(sheet);
    lv_obj_set_size(card, WIDTH, 300);
    lv_obj_align(card, LV_ALIGN_BOTTOM_MID, 0, -36);
    lv_obj_set_style_radius(card, 32, 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x1b1a21), 0);
    lv_obj_add_flag(card, LV_OBJ_FLAG_CLICKABLE); /* taps on the card stay on the card */
    sheet_name = ui_text(card, &instrument_40, 0xffffff);
    lv_obj_set_pos(sheet_name, 36, 30);
    sheet_value = ui_text(card, &instrument_52_bold, 0xffffff);
    lv_obj_align(sheet_value, LV_ALIGN_TOP_RIGHT, -36, 22);
    slider = lv_slider_create(card);
    lv_obj_set_size(slider, WIDTH - 96, 44);
    lv_obj_align(slider, LV_ALIGN_BOTTOM_MID, 0, -60);
    lv_slider_set_range(slider, 1, 100);
    lv_obj_set_style_bg_color(slider, lv_color_hex(0x2c2a34), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(slider, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(slider, 22, LV_PART_MAIN);
    lv_obj_set_style_radius(slider, 22, LV_PART_INDICATOR);
    lv_obj_set_style_pad_all(slider, 6, LV_PART_KNOB);
    lv_obj_remove_flag(slider, LV_OBJ_FLAG_GESTURE_BUBBLE); /* sliding is not swiping */
    lv_obj_add_event_cb(slider, on_slide, LV_EVENT_VALUE_CHANGED, NULL);
    lv_obj_add_event_cb(slider, on_slide_done, LV_EVENT_RELEASED, NULL);
    lv_obj_t *close = ui_text(card, &instrument_24, 0x8a8794);
    lv_label_set_text(close, "Tap beside the card to close");
    lv_obj_align(close, LV_ALIGN_BOTTOM_MID, 0, -16);

    lv_timer_create(tick, 500, NULL);
}
