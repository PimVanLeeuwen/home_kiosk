/* Headline pictures (plan.md M20): fetched from the hub only when a story's
 * picture changes, decoded by the P4's JPEG engine straight into PSRAM, and
 * handed to the screen. The screen frees the pictures it no longer shows, so a
 * picture is never freed while LVGL may still draw it. */

#include "pictures.h"

#include <stdio.h>
#include <string.h>

#include "driver/jpeg_decode.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "sdkconfig.h"

static const char *TAG = "pictures";

#define MAX_JPEG (160 * 1024)

static struct {
    char path[80];      /* what this slot shows, or is being given */
    picture_t pending;  /* decoded, not yet taken by the screen */
    bool fresh;
} slots[PICTURE_SLOTS];
static SemaphoreHandle_t lock;
static jpeg_decoder_handle_t decoder;
static SemaphoreHandle_t engine; /* the one JPEG engine, for pictures and backdrops */

bool pictures_decode_into(const uint8_t *jpeg, size_t size, uint8_t *out, size_t room, int *width, int *height)
{
    if (engine == NULL) {
        return false; /* pictures_init has not run */
    }
    xSemaphoreTake(engine, portMAX_DELAY);
    bool ok = decoder != NULL || jpeg_new_decoder_engine(&(jpeg_decode_engine_cfg_t){.timeout_ms = 200}, &decoder) == ESP_OK;
    jpeg_decode_picture_info_t info;
    ok = ok && jpeg_decoder_get_info(jpeg, size, &info) == ESP_OK && info.width > 0 &&
         (size_t)info.width * info.height * 3 <= room;
    uint32_t written = 0;
    jpeg_decode_cfg_t cfg = {.output_format = JPEG_DECODE_OUT_FORMAT_RGB888, .rgb_order = JPEG_DEC_RGB_ELEMENT_ORDER_BGR};
    ok = ok && jpeg_decoder_process(decoder, &cfg, jpeg, size, out, room, &written) == ESP_OK;
    xSemaphoreGive(engine);
    if (ok) {
        *width = info.width, *height = info.height;
    }
    return ok;
}

void pictures_init(void)
{
    if (engine == NULL) {
        engine = xSemaphoreCreateMutex();
        lock = xSemaphoreCreateMutex();
    }
}


bool pictures_fetch(const char *path, uint8_t *into, size_t room, size_t *size)
{
    char url[160];
    snprintf(url, sizeof url, "%s%s", CONFIG_PANEL_HUB_URL, path);
    esp_http_client_config_t config = {.url = url, .timeout_ms = 10000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    size_t length = 0;
    bool ok = false;
    if (esp_http_client_open(client, 0) == ESP_OK && esp_http_client_fetch_headers(client) >= 0 &&
        esp_http_client_get_status_code(client) == 200) {
        int read;
        while (length < room && (read = esp_http_client_read(client, (char *)into + length, room - length)) > 0) {
            length += read;
        }
        ok = length > 0 && length < room;
    }
    esp_http_client_cleanup(client);
    *size = length;
    return ok;
}

static bool decode(const uint8_t *jpeg, size_t size, picture_t *picture)
{
    jpeg_decode_picture_info_t info;
    if (jpeg_decoder_get_info(jpeg, size, &info) != ESP_OK || info.width == 0 || info.height == 0) {
        return false;
    }
    jpeg_decode_memory_alloc_cfg_t out_cfg = {.buffer_direction = JPEG_DEC_ALLOC_OUTPUT_BUFFER};
    size_t room = 0;
    uint8_t *pixels = jpeg_alloc_decoder_mem(info.width * info.height * 3, &out_cfg, &room);
    int width, height;
    if (pixels == NULL || !pictures_decode_into(jpeg, size, pixels, room, &width, &height)) {
        heap_caps_free(pixels);
        return false;
    }
    *picture = (picture_t){.pixels = pixels, .width = width, .height = height};
    return true;
}

void pictures_want(int slot, const char *path)
{
    if (slot < 0 || slot >= PICTURE_SLOTS) {
        return;
    }
    pictures_init();
    if (strcmp(slots[slot].path, path) == 0) {
        return;
    }
    picture_t picture = {0};
    if (path[0]) {
        jpeg_decode_memory_alloc_cfg_t in_cfg = {.buffer_direction = JPEG_DEC_ALLOC_INPUT_BUFFER};
        size_t room = 0, size = 0;
        uint8_t *jpeg = jpeg_alloc_decoder_mem(MAX_JPEG, &in_cfg, &room);
        bool ok = jpeg && pictures_fetch(path, jpeg, room, &size) && decode(jpeg, size, &picture);
        heap_caps_free(jpeg);
        if (!ok) {
            ESP_LOGW(TAG, "picture %d not loaded", slot);
            return; /* tried again with the next answer */
        }
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    heap_caps_free(slots[slot].pending.pixels); /* one the screen never took */
    slots[slot].pending = picture;
    slots[slot].fresh = true;
    snprintf(slots[slot].path, sizeof slots[slot].path, "%s", path);
    xSemaphoreGive(lock);
}

bool pictures_take(int slot, picture_t *picture)
{
    if (lock == NULL || slot < 0 || slot >= PICTURE_SLOTS) {
        return false;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    bool fresh = slots[slot].fresh;
    if (fresh) {
        *picture = slots[slot].pending;
        slots[slot].pending = (picture_t){0};
        slots[slot].fresh = false;
    }
    xSemaphoreGive(lock);
    return fresh;
}
