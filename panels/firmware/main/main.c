/* Bring-up screen for the desk panels (plan.md M16): does the display, touch,
 * Wi-Fi through the C6 and the hub all work on this board? Shows the panel's
 * name, the chip, Wi-Fi and the hub's answer, and draws a dot where touched. */

#include <stdio.h>

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_chip_info.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "lvgl.h"
#include "net.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "panel";
static lv_obj_t *info;
static lv_obj_t *dots[24];
static int next_dot;

static void update(lv_timer_t *timer)
{
    net_state_t net = net_state();
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    lv_label_set_text_fmt(
        info,
        "chip ESP32-P4 rev v%d.%d\n"
        "PSRAM free %u kB\n\n"
        "Wi-Fi  %s\n"
        "address  %s\n"
        "signal  %d dBm   drops %d\n\n"
        "hub  %d\n%s",
        chip.revision / 100, chip.revision % 100,
        (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024),
        net.connected ? "connected" : "connecting...", net.connected ? net.ip : "-", net.rssi,
        net.disconnects, net.hub_status, net.hub_note);
}

static void touched(lv_event_t *event)
{
    lv_indev_t *indev = lv_indev_active();
    if (!indev) {
        return;
    }
    lv_point_t p;
    lv_indev_get_point(indev, &p);
    lv_obj_t *dot = dots[next_dot];
    lv_obj_set_pos(dot, p.x - 14, p.y - 14);
    lv_obj_remove_flag(dot, LV_OBJ_FLAG_HIDDEN);
    next_dot = (next_dot + 1) % (int)(sizeof dots / sizeof dots[0]);
}

static void build_screen(void)
{
    lv_obj_t *screen = lv_screen_active();
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x101014), 0);
    lv_obj_add_event_cb(screen, touched, LV_EVENT_PRESSING, NULL);

    lv_obj_t *name = lv_label_create(screen);
    lv_label_set_text_fmt(name, "Panel: %s", CONFIG_PANEL_NAME);
    lv_obj_set_style_text_font(name, &lv_font_montserrat_48, 0);
    lv_obj_set_style_text_color(name, lv_color_hex(0xb4a9ff), 0);
    lv_obj_align(name, LV_ALIGN_TOP_LEFT, 40, 40);

    info = lv_label_create(screen);
    lv_obj_set_style_text_font(info, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(info, lv_color_hex(0xecedef), 0);
    lv_obj_align(info, LV_ALIGN_TOP_LEFT, 40, 130);

    lv_obj_t *hint = lv_label_create(screen);
    lv_label_set_text(hint, "Touch anywhere: a dot follows your finger");
    lv_obj_set_style_text_font(hint, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(hint, lv_color_hex(0x7d7a8c), 0);
    lv_obj_align(hint, LV_ALIGN_BOTTOM_LEFT, 40, -40);

    for (int i = 0; i < (int)(sizeof dots / sizeof dots[0]); i++) {
        dots[i] = lv_obj_create(screen);
        lv_obj_set_size(dots[i], 28, 28);
        lv_obj_set_style_radius(dots[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(dots[i], lv_color_hex(0x9c8ffb), 0);
        lv_obj_set_style_border_width(dots[i], 0, 0);
        lv_obj_remove_flag(dots[i], LV_OBJ_FLAG_CLICKABLE);
        lv_obj_add_flag(dots[i], LV_OBJ_FLAG_HIDDEN);
    }

    lv_timer_create(update, 1000, NULL);
    update(NULL);
}

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_ERROR_CHECK(bsp_display_start() != NULL ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(bsp_display_backlight_on());
    ESP_ERROR_CHECK(bsp_display_brightness_set(60));
    ESP_ERROR_CHECK(bsp_display_lock(0) ? ESP_OK : ESP_ERR_TIMEOUT);
    build_screen();
    bsp_display_unlock();

    ESP_LOGI(TAG, "panel %s starting Wi-Fi", CONFIG_PANEL_NAME);
    net_start();
}
