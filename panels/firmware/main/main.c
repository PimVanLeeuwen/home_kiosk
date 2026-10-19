/* The desk panels' firmware (plan.md M16): one build for every board; the hub
 * says which panel a board is. Screens so far: the Now panel's clock with the
 * next two hours of rain, the morning train and the day view (plan.md M20),
 * the board's own screen, and the start-up screen until the hub has answered. */

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "desk.h"
#include "esp_app_desc.h"
#include "devshot.h"
#include "esp_log.h"
#include "net.h"
#include "nvs_flash.h"
#include "screens.h"
#include "update.h"
#include "sdkconfig.h"

static const char *TAG = "panel";

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    /* Turned a quarter to the right, so the USB ports sit at the top in the
     * printed cases; touch follows: mirrored across, then x and y swapped. */
    bsp_display_cfg_t display = {
        .lv_adapter_cfg = ESP_LV_ADAPTER_DEFAULT_CONFIG(),
        .rotation = ESP_LV_ADAPTER_ROTATE_90,
        .tear_avoid_mode = ESP_LV_ADAPTER_TEAR_AVOID_MODE_TRIPLE_PARTIAL,
        .touch_flags = {.swap_xy = 1, .mirror_x = 1},
    };
    ESP_ERROR_CHECK(bsp_display_start_with_config(&display) != NULL ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(bsp_display_backlight_on());
    ESP_ERROR_CHECK(bsp_display_brightness_set(PANEL_BRIGHTNESS));
    /* The board package logs every brightness change: quiet it for the dips between screens. */
    esp_log_level_set("ESP32_P4_4B", ESP_LOG_WARN);
    /* Wait for LVGL's first frame: with this board package 0 means "do not wait". */
    ESP_ERROR_CHECK(bsp_display_lock(5000) ? ESP_OK : ESP_ERR_TIMEOUT);
    screens_start();
    bsp_display_unlock();

    ESP_LOGI(TAG, "board %s starting, firmware %s", desk_mac(), esp_app_get_description()->version);
    net_start();
    desk_start();
    update_start();
    devshot_start();
}
