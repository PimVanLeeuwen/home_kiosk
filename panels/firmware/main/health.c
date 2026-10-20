/* The panel's health line (see health.h), from its own task: it does not need
 * LVGL to run, so it also tells when LVGL has stopped. */

#include "health.h"

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "screens.h"

static const char *TAG = "health";

#define EVERY_MS (30 * 1000)

static void health_task(void *arg)
{
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(EVERY_MS));
        /* Can we get the display lock? If LVGL is stuck holding it, no. */
        bool lock = bsp_display_lock(2000);
        if (lock) {
            bsp_display_unlock();
        }
        screens_state_t s = screens_state();
        ESP_LOGI(TAG, "internal %u kB (largest %u), psram %u kB; lvgl beats %lu frames %lu lock %s; "
                 "screen %d coming %d waiting %d turns %lu; touches %lu held %d",
                 (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024),
                 (unsigned)(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL) / 1024),
                 (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024), (unsigned long)s.beats,
                 (unsigned long)s.frames, lock ? "ok" : "BUSY", s.current, s.coming, s.waiting,
                 (unsigned long)s.turns, (unsigned long)s.touches, s.held);
    }
}

void health_start(void)
{
    xTaskCreate(health_task, "health", 3072, NULL, 1, NULL);
}
