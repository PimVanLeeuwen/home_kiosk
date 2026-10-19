/* The hub's answer for this panel: GET /api/desk/<name> every 30 s. It also
 * carries the hub's time, so the panel never contacts the internet: the clock
 * is set from it whenever it is off by more than a second. */

#include "desk.h"

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "sdkconfig.h"

static const char *TAG = "desk";
static desk_clock_t clock_state;
static SemaphoreHandle_t lock;

#define BODY_MAX 4096
#define EVERY_MS 30000

desk_clock_t desk_clock(void)
{
    desk_clock_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = clock_state;
    xSemaphoreGive(lock);
    return copy;
}

static void copy_string(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static void set_time(const cJSON *time)
{
    const cJSON *epoch = cJSON_GetObjectItem(time, "epoch");
    if (!cJSON_IsNumber(epoch)) {
        return;
    }
    struct timeval now;
    gettimeofday(&now, NULL);
    double hub = epoch->valuedouble;
    double ours = now.tv_sec + now.tv_usec / 1e6;
    if (fabs(hub - ours) > 1.0) {
        struct timeval set = {.tv_sec = (time_t)hub, .tv_usec = (suseconds_t)((hub - floor(hub)) * 1e6)};
        settimeofday(&set, NULL);
        ESP_LOGI(TAG, "clock set from the hub (was off by %.1f s)", hub - ours);
    }
}

static void apply(const char *body)
{
    cJSON *root = cJSON_Parse(body);
    if (root == NULL) {
        ESP_LOGW(TAG, "unreadable answer");
        return;
    }
    const cJSON *time = cJSON_GetObjectItem(root, "time");
    set_time(time);

    desk_clock_t next = {.present = true};
    const cJSON *offset = cJSON_GetObjectItem(time, "utc_offset");
    next.utc_offset = cJSON_IsNumber(offset) ? offset->valueint : 0;

    const cJSON *screen;
    cJSON_ArrayForEach(screen, cJSON_GetObjectItem(root, "screens"))
    {
        const cJSON *kind = cJSON_GetObjectItem(screen, "kind");
        if (!cJSON_IsString(kind) || strcmp(kind->valuestring, "clock") != 0) {
            continue;
        }
        next.stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
        next.wet = cJSON_IsTrue(cJSON_GetObjectItem(screen, "wet"));
        copy_string(next.place, sizeof next.place, cJSON_GetObjectItem(screen, "place"));
        copy_string(next.date, sizeof next.date, cJSON_GetObjectItem(screen, "date"));
        copy_string(next.description, sizeof next.description, cJSON_GetObjectItem(screen, "description"));
        copy_string(next.rain_line, sizeof next.rain_line, cJSON_GetObjectItem(screen, "rain_line"));
        const cJSON *temperature = cJSON_GetObjectItem(screen, "temperature");
        next.has_temperature = cJSON_IsNumber(temperature);
        next.temperature = next.has_temperature ? temperature->valueint : 0;
        const cJSON *value;
        cJSON_ArrayForEach(value, cJSON_GetObjectItem(screen, "rain"))
        {
            if (next.rain_count < DESK_RAIN_MAX && cJSON_IsNumber(value)) {
                next.rain[next.rain_count++] = (float)value->valuedouble;
            }
        }
    }
    cJSON_Delete(root);

    xSemaphoreTake(lock, portMAX_DELAY);
    next.version = clock_state.version + 1;
    clock_state = next;
    xSemaphoreGive(lock);
}

static void desk_task(void *arg)
{
    char url[160];
    snprintf(url, sizeof url, "%s/api/desk/%s", CONFIG_PANEL_HUB_URL, CONFIG_PANEL_NAME);
    char *body = malloc(BODY_MAX);
    for (;;) {
        if (net_state().connected) {
            esp_http_client_config_t config = {.url = url, .timeout_ms = 5000};
            esp_http_client_handle_t client = esp_http_client_init(&config);
            int status = 0, length = 0;
            if (esp_http_client_open(client, 0) == ESP_OK) {
                esp_http_client_fetch_headers(client);
                status = esp_http_client_get_status_code(client);
                int read;
                while (length < BODY_MAX - 1 &&
                       (read = esp_http_client_read(client, body + length, BODY_MAX - 1 - length)) > 0) {
                    length += read;
                }
            }
            esp_http_client_cleanup(client);
            body[length] = '\0';
            net_note_hub(status);
            if (status == 200) {
                apply(body);
            } else {
                ESP_LOGW(TAG, "hub answered %d", status);
            }
        }
        /* Soon after Wi-Fi comes up, then every 30 s. */
        vTaskDelay(pdMS_TO_TICKS(desk_clock().present ? EVERY_MS : 3000));
    }
}

void desk_start(void)
{
    lock = xSemaphoreCreateMutex();
    xTaskCreate(desk_task, "desk", 8192, NULL, 4, NULL);
}
