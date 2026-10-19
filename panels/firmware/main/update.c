/* Updates over Wi-Fi from the hub (plan.md M16). The dashboard image serves the
 * firmware CI built for every board: /panels/firmware.json ({"version",
 * "size"}) and /panels/firmware.bin. A board with a different version installs
 * it into its other app slot between 04:00 and 05:00 (local time, from the
 * hub), so it never restarts while someone looks at it, and restarts into it.
 *
 * The bootloader keeps the old slot until the new firmware has reached the hub
 * once (update_hub_answered); one that does not within 5 minutes is rolled
 * back. Every board follows the hub's firmware, bench builds too: "update" on
 * the serial console installs it at once. CI versions the firmware with git's
 * hash of panels/firmware, so a push that leaves it alone changes nothing. The image is checked by ESP-IDF (its chip, revision
 * and the SHA-256 it carries); there is no signature: the hub is LAN only. */

#include "update.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

#include "cJSON.h"
#include "desk.h"
#include "esp_app_desc.h"
#include "esp_http_client.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "sdkconfig.h"

static const char *TAG = "update";

#define CHECK_MS (10 * 60 * 1000)
#define WINDOW_HOUR 4                   /* 04:00 to 05:00 */
#define TRIAL_MS (5 * 60 * 1000)       /* for a new firmware to reach the hub */
#define MANIFEST_MAX 512
#define MAX_IMAGE (8 * 1024 * 1024)    /* an app slot */

static SemaphoreHandle_t wake;
static volatile bool forced, on_trial, busy;

bool update_busy(void)
{
    return busy;
}

void update_hub_answered(void)
{
    if (on_trial) {
        on_trial = false;
        esp_ota_mark_app_valid_cancel_rollback();
        ESP_LOGI(TAG, "firmware %s reached the hub: kept", esp_app_get_description()->version);
    }
}

void update_now(void)
{
    forced = true;
    if (wake != NULL) {
        xSemaphoreGive(wake);
    }
}

static bool in_window(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (tv.tv_sec < 1700000000) {
        return false; /* no time from the hub yet */
    }
    time_t local = tv.tv_sec + desk_clock().utc_offset;
    struct tm t;
    gmtime_r(&local, &t);
    return t.tm_hour == WINDOW_HOUR;
}

/* The version the hub offers and its size; "" when it offers none or cannot be asked. */
static void offered(char *version, size_t size, int *bytes)
{
    version[0] = '\0';
    char url[160], body[MANIFEST_MAX];
    snprintf(url, sizeof url, "%s/panels/firmware.json", CONFIG_PANEL_HUB_URL);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 10000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    int length = 0;
    if (esp_http_client_open(client, 0) == ESP_OK && esp_http_client_fetch_headers(client) >= 0 &&
        esp_http_client_get_status_code(client) == 200) {
        int read;
        while (length < MANIFEST_MAX - 1 &&
               (read = esp_http_client_read(client, body + length, MANIFEST_MAX - 1 - length)) > 0) {
            length += read;
        }
    }
    esp_http_client_cleanup(client);
    body[length] = '\0';
    cJSON *root = cJSON_Parse(body);
    const cJSON *value = cJSON_GetObjectItem(root, "version");
    const cJSON *image_size = cJSON_GetObjectItem(root, "size");
    if (cJSON_IsString(value) && cJSON_IsNumber(image_size)) {
        snprintf(version, size, "%s", value->valuestring);
        *bytes = image_size->valueint;
    }
    cJSON_Delete(root);
}

/* Download first, into PSRAM, then write to flash with the network quiet:
 * writing flash pauses the caches, and doing it during the download broke the
 * link to the Wi-Fi chip (its old factory firmware) and restarted the board. */
static void install(const char *version, int size)
{
    if (size <= 0 || size > MAX_IMAGE) {
        ESP_LOGW(TAG, "firmware %s has an unlikely size (%d bytes)", version, size);
        return;
    }
    uint8_t *image = heap_caps_malloc(size, MALLOC_CAP_SPIRAM);
    if (image == NULL) {
        ESP_LOGW(TAG, "no memory for firmware %s", version);
        return;
    }
    char url[160];
    snprintf(url, sizeof url, "%s/panels/firmware.bin", CONFIG_PANEL_HUB_URL);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 15000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    int length = 0;
    ESP_LOGI(TAG, "downloading firmware %s (%d bytes)", version, size);
    if (esp_http_client_open(client, 0) == ESP_OK && esp_http_client_fetch_headers(client) >= 0 &&
        esp_http_client_get_status_code(client) == 200) {
        int read;
        while (length < size && (read = esp_http_client_read(client, (char *)image + length, size - length)) > 0) {
            length += read;
        }
    }
    esp_http_client_cleanup(client);
    if (length != size) {
        ESP_LOGW(TAG, "downloading firmware %s stopped at %d of %d bytes", version, length, size);
        heap_caps_free(image);
        return;
    }

    busy = true;
    vTaskDelay(pdMS_TO_TICKS(1000)); /* let a hub request in flight finish */
    const esp_partition_t *slot = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t ota;
    esp_err_t err = esp_ota_begin(slot, size, &ota);
    if (err == ESP_OK) {
        err = esp_ota_write(ota, image, size);
        esp_err_t end = esp_ota_end(ota); /* checks the image */
        err = err == ESP_OK ? end : err;
    }
    if (err == ESP_OK) {
        err = esp_ota_set_boot_partition(slot);
    }
    heap_caps_free(image);
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "firmware %s installed, restarting", version);
        vTaskDelay(pdMS_TO_TICKS(500));
        esp_restart();
    }
    busy = false;
    ESP_LOGW(TAG, "installing firmware %s failed: %s", version, esp_err_to_name(err));
}

static void update_task(void *arg)
{
    const char *own = esp_app_get_description()->version;
    TickType_t started = xTaskGetTickCount();
    for (;;) {
        xSemaphoreTake(wake, pdMS_TO_TICKS(on_trial ? 10000 : CHECK_MS));
        if (on_trial && xTaskGetTickCount() - started > pdMS_TO_TICKS(TRIAL_MS)) {
            ESP_LOGE(TAG, "firmware %s never reached the hub: back to the previous one", own);
            esp_ota_mark_app_invalid_rollback_and_reboot();
        }
        bool asked = forced;
        forced = false;
        if (on_trial || !net_state().connected) {
            continue;
        }
        if (!asked && !in_window()) {
            continue;
        }
        char version[40];
        int bytes = 0;
        offered(version, sizeof version, &bytes);
        if (version[0] == '\0') {
            ESP_LOGW(TAG, "the hub offers no firmware");
        } else if (strcmp(version, own) == 0) {
            ESP_LOGI(TAG, "firmware %s is the newest", own);
        } else {
            install(version, bytes);
        }
    }
}

void update_start(void)
{
    esp_ota_img_states_t state;
    const esp_partition_t *running = esp_ota_get_running_partition();
    on_trial = esp_ota_get_state_partition(running, &state) == ESP_OK && state == ESP_OTA_IMG_PENDING_VERIFY;
    if (on_trial) {
        ESP_LOGI(TAG, "firmware %s is new: on trial until it reaches the hub", esp_app_get_description()->version);
    }
    wake = xSemaphoreCreateBinary();
    xTaskCreate(update_task, "update", 8192, NULL, 3, NULL);
}
