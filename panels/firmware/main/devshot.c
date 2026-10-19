/* A developer's screenshot over the USB serial console: type "shot" and the
 * panel answers with its screen, run-length-encoded RGB888, as numbered base64
 * lines with a checksum each ("L<n> <base64> <crc32>"), between
 * "SHOT <width> <height> <bytes> <lines>" and "END". Other parts of the firmware
 * can print in between, so panels/tools/shot.py keeps the good lines and asks
 * again for the rest. "next" turns to the next screen and "hold" keeps the current one for a
 * minute, to capture each screen. */

#include "devshot.h"

#include <stdio.h>
#include <string.h>

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_rom_crc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "screens.h"

static const char *TAG = "devshot";
static const char B64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
#define CHUNK 57 /* bytes per line: 76 base64 characters */

static size_t encode(const uint8_t *in, size_t len, char *out)
{
    size_t o = 0;
    for (size_t i = 0; i < len; i += 3) {
        uint32_t n = (uint32_t)in[i] << 16 | (i + 1 < len ? in[i + 1] << 8 : 0) | (i + 2 < len ? in[i + 2] : 0);
        out[o++] = B64[(n >> 18) & 63];
        out[o++] = B64[(n >> 12) & 63];
        out[o++] = i + 1 < len ? B64[(n >> 6) & 63] : '=';
        out[o++] = i + 2 < len ? B64[n & 63] : '=';
    }
    out[o] = '\0';
    return o;
}

/* Run-length groups (count, B, G, R) with a 16-bit little-endian count, into PSRAM. */
static uint8_t *compress(const lv_draw_buf_t *shot, size_t *size)
{
    uint32_t w = shot->header.w, h = shot->header.h, stride = shot->header.stride;
    uint8_t *out = heap_caps_malloc((size_t)w * h * 5, MALLOC_CAP_SPIRAM);
    if (out == NULL) {
        return NULL;
    }
    size_t n = 0;
    uint32_t last = 0, count = 0;
    for (uint32_t y = 0; y < h; y++) {
        const uint8_t *row = shot->data + y * stride;
        for (uint32_t x = 0; x < w; x++) {
            uint32_t px = row[3 * x] | row[3 * x + 1] << 8 | (uint32_t)row[3 * x + 2] << 16;
            if (count && px == last && count < 0xffff) {
                count++;
                continue;
            }
            if (count) {
                out[n++] = count & 0xff, out[n++] = count >> 8;
                out[n++] = last & 0xff, out[n++] = (last >> 8) & 0xff, out[n++] = last >> 16;
            }
            last = px;
            count = 1;
        }
    }
    out[n++] = count & 0xff, out[n++] = count >> 8;
    out[n++] = last & 0xff, out[n++] = (last >> 8) & 0xff, out[n++] = last >> 16;
    *size = n;
    return out;
}

static void send_screen(void)
{
    if (!bsp_display_lock(1000)) {
        ESP_LOGW(TAG, "the screen is busy");
        return;
    }
    lv_draw_buf_t *shot = lv_snapshot_take(lv_screen_active(), LV_COLOR_FORMAT_RGB888);
    bsp_display_unlock();
    if (shot == NULL) {
        ESP_LOGW(TAG, "no memory for a snapshot");
        return;
    }
    size_t size = 0;
    uint8_t *data = compress(shot, &size);
    uint32_t w = shot->header.w, h = shot->header.h;
    lv_draw_buf_destroy(shot);
    if (data == NULL) {
        ESP_LOGW(TAG, "no memory to compress the snapshot");
        return;
    }

    size_t lines = (size + CHUNK - 1) / CHUNK;
    char text[80];
    /* Logging stays on (switching it off mid-transfer locked up core 0); a line
     * broken by other output fails its checksum and is asked for again. */
    printf("\nSHOT %lu %lu %u %u\n", (unsigned long)w, (unsigned long)h, (unsigned)size, (unsigned)lines);
    for (size_t i = 0; i < lines; i++) {
        size_t len = size - i * CHUNK < CHUNK ? size - i * CHUNK : CHUNK;
        encode(data + i * CHUNK, len, text);
        printf("L%u %s %08lx\n", (unsigned)i, text, (unsigned long)esp_rom_crc32_le(0, data + i * CHUNK, len));
        fflush(stdout);
        /* The console busy-waits on the UART: give the CPU back after every line. */
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    printf("END\n");
    fflush(stdout);
    heap_caps_free(data);
}

static void devshot_task(void *arg)
{
    char line[16];
    size_t len = 0;
    for (;;) {
        /* The console as ESP-IDF sets it up: reading never blocks, so poll. */
        int c = fgetc(stdin);
        if (c == EOF) {
            clearerr(stdin);
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (c == '\n' || c == '\r') {
            line[len] = '\0';
            /* A reset can leave a stray byte in front of it. */
            if (len >= 4 && strcmp(line + len - 4, "shot") == 0) {
                send_screen();
            } else if (len >= 4 && strcmp(line + len - 4, "next") == 0 && bsp_display_lock(1000)) {
                screens_next();
                bsp_display_unlock();
            } else if (len >= 4 && strcmp(line + len - 4, "hold") == 0) {
                screens_hold();
            }
            len = 0;
        } else if (len < sizeof line - 1) {
            line[len++] = (char)c;
        }
    }
}

void devshot_start(void)
{
    /* No UART driver: installing one on the console port stalls its output. */
    xTaskCreate(devshot_task, "devshot", 4096, NULL, 2, NULL);
    ESP_LOGI(TAG, "listening for \"shot\", \"next\" and \"hold\"");
}
