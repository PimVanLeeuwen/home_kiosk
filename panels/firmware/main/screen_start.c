/* The start-up screen (plan.md M16): from power-on (or an update) until the
 * hub's first answer, instead of an empty clock. Three violet dots pulse one
 * after another while one line says what the board is doing; after 30 s
 * without the hub it says plainly what is wrong, with the board's MAC. The
 * screens.c rotation leaves it with the usual dip through black.
 *
 * The animation is three small dots, as LVGL redraws only what changes: a
 * full-screen animation runs at about 6 frames a second on these boards. */

#include "screen_start.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_timer.h"
#include "lvgl.h"
#include "net.h"
#include "sdkconfig.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define PROBLEM_AFTER_US (30 * 1000 * 1000)
#define DOT 20
#define PULSE_MS 700

static lv_obj_t *dots, *warning, *line, *detail;

static lv_obj_t *centred(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = ui_text(parent, font, colour);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    return label;
}

static void set_opa(void *dot, int32_t opa)
{
    lv_obj_set_style_bg_opa(dot, (lv_opa_t)opa, 0);
}

/* The hub's address without "http://", as the owner would type it. */
static const char *hub_host(void)
{
    const char *url = CONFIG_PANEL_HUB_URL;
    const char *host = strstr(url, "://");
    return host ? host + 3 : url;
}

static void show(const char *what, const char *more, bool problem)
{
    lv_label_set_text(line, what);
    lv_label_set_text(detail, more);
    lv_obj_set_flag(dots, LV_OBJ_FLAG_HIDDEN, problem);
    lv_obj_set_flag(warning, LV_OBJ_FLAG_HIDDEN, !problem);
}

static void tick(lv_timer_t *timer)
{
    net_state_t net = net_state();
    bool late = esp_timer_get_time() > PROBLEM_AFTER_US;
    char more[64];
    if (net.no_network) {
        show("No Wi-Fi network saved", "Flash this board once over USB", true);
    } else if (!net.connected) {
        show(late ? "Can't join the Wi-Fi" : "Connecting to Wi-Fi", late ? "Trying again" : "", late);
    } else if (late && net.hub_status != 0) {
        snprintf(more, sizeof more, "%s answered %d · trying again", hub_host(), net.hub_status);
        show("The hub is not ready", more, true);
    } else if (late) {
        snprintf(more, sizeof more, "%s · trying again", hub_host());
        show("Can't reach the hub", more, true);
    } else {
        show("Asking the hub", "", false);
    }
}

void screen_start_create(lv_obj_t *screen)
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

    lv_obj_t *header = centred(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "DESK PANEL");
    lv_obj_align(header, LV_ALIGN_TOP_LEFT, 36, 24);

    /* Three dots that brighten one after another. */
    dots = lv_obj_create(screen);
    lv_obj_remove_style_all(dots);
    lv_obj_set_size(dots, 3 * DOT + 2 * DOT, DOT);
    lv_obj_align(dots, LV_ALIGN_CENTER, 0, -40);
    for (int i = 0; i < 3; i++) {
        lv_obj_t *dot = lv_obj_create(dots);
        lv_obj_remove_style_all(dot);
        lv_obj_set_size(dot, DOT, DOT);
        lv_obj_set_pos(dot, i * 2 * DOT, 0);
        lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(dot, lv_color_hex(0xb4a9ff), 0);
        lv_obj_set_style_bg_opa(dot, 50, 0);
        lv_anim_t anim;
        lv_anim_init(&anim);
        lv_anim_set_var(&anim, dot);
        lv_anim_set_exec_cb(&anim, set_opa);
        lv_anim_set_values(&anim, 50, 255);
        lv_anim_set_duration(&anim, PULSE_MS);
        lv_anim_set_reverse_duration(&anim, PULSE_MS);
        lv_anim_set_delay(&anim, i * 200);
        lv_anim_set_repeat_delay(&anim, 200);
        lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
        lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
        lv_anim_start(&anim);
    }

    /* In place of the dots when something is wrong: a calm amber dot. */
    warning = lv_obj_create(screen);
    lv_obj_remove_style_all(warning);
    lv_obj_set_size(warning, 28, 28);
    lv_obj_set_style_radius(warning, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(warning, lv_color_hex(0xe2a35a), 0);
    lv_obj_set_style_bg_opa(warning, LV_OPA_COVER, 0);
    lv_obj_align(warning, LV_ALIGN_CENTER, 0, -40);
    lv_obj_add_flag(warning, LV_OBJ_FLAG_HIDDEN);

    line = centred(screen, &instrument_40, 0xffffff);
    lv_obj_align(line, LV_ALIGN_CENTER, 0, 40);
    detail = centred(screen, &instrument_24, 0x9b98a8);
    lv_obj_align(detail, LV_ALIGN_CENTER, 0, 96);

    lv_obj_t *mac = centred(screen, &instrument_24, 0x6f6c7d);
    lv_label_set_text(mac, desk_mac());
    lv_obj_align(mac, LV_ALIGN_BOTTOM_MID, 0, -24);

    lv_timer_create(tick, 500, NULL);
    tick(NULL);
}
