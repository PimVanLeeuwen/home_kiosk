/* The desk panels' firmware (plan.md M16). For now the Now panel's two
 * screens: the clock with the next two hours of rain, and the day view
 * (plan.md M20). */

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "desk.h"
#include "devshot.h"
#include "esp_log.h"
#include "net.h"
#include "nvs_flash.h"
#include "screens.h"
#include "sdkconfig.h"

static const char *TAG = "panel";

/* The panels run bright (the owner's choice); true black backgrounds keep the IPS
 * glow down. At 40 % the backlight of one board stayed off altogether. */
#define BRIGHTNESS 100

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_ERROR_CHECK(bsp_display_start() != NULL ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(bsp_display_backlight_on());
    ESP_ERROR_CHECK(bsp_display_brightness_set(BRIGHTNESS));
    /* Wait for LVGL's first frame: with this board package 0 means "do not wait". */
    ESP_ERROR_CHECK(bsp_display_lock(5000) ? ESP_OK : ESP_ERR_TIMEOUT);
    screens_start();
    bsp_display_unlock();

    ESP_LOGI(TAG, "panel %s starting", CONFIG_PANEL_NAME);
    net_start();
    desk_start();
    devshot_start();
}
