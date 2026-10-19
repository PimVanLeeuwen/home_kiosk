/* A board's own screen (plan.md M16): shown when the hub has no panel for this
 * board ("Which panel is this?") or the panel has no screens yet. The MAC is
 * the one written on the board's back and listed in Settings, Desk panels.
 * Quiet violet light from the top, as House will have. */

#include "screen_board.h"

#include "desk.h"
#include "esp_app_desc.h"
#include "lvgl.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

static lv_obj_t *title, *mac, *hint;
static uint32_t shown = UINT32_MAX;

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(label, "");
    return label;
}

static void tick(lv_timer_t *timer)
{
    desk_board_t board = desk_board();
    if (board.version == shown) {
        return;
    }
    shown = board.version;
    lv_label_set_text(title, board.listed ? board.title : "Which panel is this?");
    lv_label_set_text(mac, board.listed && board.mac[0] ? board.mac : desk_mac());
    lv_label_set_text(hint, board.hint);
}

void screen_board_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 70, 0);

    lv_obj_t *header = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "DESK PANEL");
    lv_obj_align(header, LV_ALIGN_TOP_LEFT, 36, 24);

    title = text(screen, &instrument_40, 0xffffff);
    lv_obj_align(title, LV_ALIGN_CENTER, 0, -96);

    /* The address in a soft violet pill: what to find in Settings. */
    lv_obj_t *pill = lv_obj_create(screen);
    lv_obj_remove_style_all(pill);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 32, 0);
    lv_obj_set_style_pad_ver(pill, 18, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_color(pill, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_bg_opa(pill, 36, 0);
    lv_obj_set_style_border_color(pill, lv_color_hex(0x8f80ff), 0);
    lv_obj_set_style_border_opa(pill, 110, 0);
    lv_obj_set_style_border_width(pill, 2, 0);
    lv_obj_align(pill, LV_ALIGN_CENTER, 0, 0);
    mac = text(pill, &instrument_40, 0xd6cfff);
    lv_obj_set_style_text_letter_space(mac, 3, 0);

    hint = text(screen, &instrument_24, 0x9b98a8);
    lv_obj_set_width(hint, 560);
    lv_label_set_long_mode(hint, LV_LABEL_LONG_WRAP);
    lv_obj_align(hint, LV_ALIGN_CENTER, 0, 96);

    lv_obj_t *firmware = text(screen, &instrument_24, 0x6f6c7d);
    lv_label_set_text_fmt(firmware, "Firmware %s", esp_app_get_description()->version);
    lv_obj_align(firmware, LV_ALIGN_BOTTOM_MID, 0, -24);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
