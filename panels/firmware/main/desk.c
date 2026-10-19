/* The hub's answer for this board: GET /api/desk/board/<MAC>?firmware=<version>
 * every 30 s; the hub knows which panel the board is. It also
 * carries the hub's time, so the panel never contacts the internet: the clock
 * is set from it whenever it is off by more than a second. */

#include "desk.h"
#include "esp_attr.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>

#include "cJSON.h"
#include "esp_app_desc.h"
#include "esp_mac.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "update.h"
#include "sdkconfig.h"

static const char *TAG = "desk";
/* The hub's latest answer, in PSRAM: internal RAM is for the Wi-Fi buffers. */
EXT_RAM_BSS_ATTR static desk_clock_t clock_state;
EXT_RAM_BSS_ATTR static desk_day_t day_state;
EXT_RAM_BSS_ATTR static desk_board_t board_state;
EXT_RAM_BSS_ATTR static desk_train_t train_state;
EXT_RAM_BSS_ATTR static desk_agenda_t agenda_state;
static char mac_text[18];
static SemaphoreHandle_t lock;

#define BODY_MAX 8192
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

desk_day_t desk_day(void)
{
    desk_day_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = day_state;
    xSemaphoreGive(lock);
    return copy;
}

desk_board_t desk_board(void)
{
    desk_board_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = board_state;
    xSemaphoreGive(lock);
    return copy;
}

static void copy_string(char *to, size_t size, const cJSON *from);
static int number(const cJSON *from, int otherwise);

desk_train_t desk_train(void)
{
    desk_train_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = train_state;
    xSemaphoreGive(lock);
    return copy;
}

desk_agenda_t desk_agenda(void)
{
    desk_agenda_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = agenda_state;
    xSemaphoreGive(lock);
    return copy;
}

static bool has(const bool *present)
{
    if (lock == NULL) {
        return false;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    bool yes = *present;
    xSemaphoreGive(lock);
    return yes;
}

bool desk_has_day(void)
{
    return has(&day_state.present);
}

bool desk_has_train(void)
{
    return has(&train_state.present);
}

bool desk_has_agenda(void)
{
    return has(&agenda_state.present);
}

/* "#ff8d28" as 0xff8d28; the hub's violet when missing. */
static uint32_t colour(const cJSON *from)
{
    if (!cJSON_IsString(from) || from->valuestring[0] != '#') {
        return 0x8f80ff;
    }
    return (uint32_t)strtoul(from->valuestring + 1, NULL, 16);
}

static void parse_agenda(const cJSON *screen, desk_agenda_t *agenda)
{
    const cJSON *item;
    agenda->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    agenda->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!agenda->present) {
        return;
    }
    copy_string(agenda->title, sizeof agenda->title, cJSON_GetObjectItem(screen, "title"));
    copy_string(agenda->count, sizeof agenda->count, cJSON_GetObjectItem(screen, "count"));
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "events"))
    {
        if (agenda->event_count == DESK_AGENDA_EVENTS) {
            break;
        }
        typeof(agenda->events[0]) *e = &agenda->events[agenda->event_count++];
        copy_string(e->title, sizeof e->title, cJSON_GetObjectItem(item, "title"));
        copy_string(e->calendar, sizeof e->calendar, cJSON_GetObjectItem(item, "calendar"));
        e->color = colour(cJSON_GetObjectItem(item, "color"));
        const cJSON *at = cJSON_GetObjectItem(item, "start_at");
        e->start_at = cJSON_IsNumber(at) ? (int64_t)at->valuedouble : 0;
        at = cJSON_GetObjectItem(item, "end_at");
        e->end_at = cJSON_IsNumber(at) ? (int64_t)at->valuedouble : e->start_at;
        e->start_minute = number(cJSON_GetObjectItem(item, "start_minute"), 0);
        e->end_minute = number(cJSON_GetObjectItem(item, "end_minute"), e->start_minute);
        copy_string(e->start, sizeof e->start, cJSON_GetObjectItem(item, "start"));
        copy_string(e->end, sizeof e->end, cJSON_GetObjectItem(item, "end"));
    }
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "all_day"))
    {
        if (agenda->all_day_count == DESK_AGENDA_ALL_DAY) {
            break;
        }
        int i = agenda->all_day_count++;
        copy_string(agenda->all_day[i].title, sizeof agenda->all_day[i].title, cJSON_GetObjectItem(item, "title"));
        agenda->all_day[i].color = colour(cJSON_GetObjectItem(item, "color"));
    }
}

static void parse_train(const cJSON *screen, desk_train_t *train)
{
    const cJSON *item;
    train->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    train->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!train->present) {
        return;
    }
    copy_string(train->title, sizeof train->title, cJSON_GetObjectItem(screen, "title"));
    copy_string(train->departure, sizeof train->departure, cJSON_GetObjectItem(screen, "departure"));
    copy_string(train->departure_now, sizeof train->departure_now, cJSON_GetObjectItem(screen, "departure_now"));
    train->gone = cJSON_IsTrue(cJSON_GetObjectItem(screen, "gone"));
    copy_string(train->status, sizeof train->status, cJSON_GetObjectItem(screen, "status"));
    item = cJSON_GetObjectItem(screen, "tone");
    train->tone = !cJSON_IsString(item)                  ? DESK_TONE_WARN
                  : strcmp(item->valuestring, "up") == 0   ? DESK_TONE_UP
                  : strcmp(item->valuestring, "down") == 0 ? DESK_TONE_DOWN
                                                           : DESK_TONE_WARN;
    copy_string(train->sub, sizeof train->sub, cJSON_GetObjectItem(screen, "sub"));
    copy_string(train->platform, sizeof train->platform, cJSON_GetObjectItem(screen, "platform"));
    copy_string(train->platform_was, sizeof train->platform_was, cJSON_GetObjectItem(screen, "platform_was"));
    item = cJSON_GetObjectItem(screen, "leaves_at");
    train->leaves_at = cJSON_IsNumber(item) ? (int64_t)item->valuedouble : 0;
    copy_string(train->ring_label, sizeof train->ring_label, cJSON_GetObjectItem(screen, "ring_label"));
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "stops"))
    {
        if (train->stop_count == DESK_TRAIN_STOPS) {
            break;
        }
        int i = train->stop_count++;
        copy_string(train->stops[i].time, sizeof train->stops[i].time, cJSON_GetObjectItem(item, "time"));
        copy_string(train->stops[i].name, sizeof train->stops[i].name, cJSON_GetObjectItem(item, "name"));
        train->stops[i].shifted = cJSON_IsTrue(cJSON_GetObjectItem(item, "shifted"));
        train->stops[i].cancelled = cJSON_IsTrue(cJSON_GetObjectItem(item, "cancelled"));
    }
    item = cJSON_GetObjectItem(screen, "next");
    if ((train->has_next = cJSON_IsObject(item))) {
        copy_string(train->next_departure, sizeof train->next_departure, cJSON_GetObjectItem(item, "departure"));
        copy_string(train->next_platform, sizeof train->next_platform, cJSON_GetObjectItem(item, "platform"));
        copy_string(train->next_arrives, sizeof train->next_arrives, cJSON_GetObjectItem(item, "arrives"));
    }
    item = cJSON_GetObjectItem(screen, "notice");
    if ((train->has_notice = cJSON_IsObject(item))) {
        copy_string(train->notice_title, sizeof train->notice_title, cJSON_GetObjectItem(item, "title"));
        copy_string(train->notice_text, sizeof train->notice_text, cJSON_GetObjectItem(item, "text"));
    }
}

const char *desk_mac(void)
{
    if (mac_text[0] == '\0') {
        /* The chip's own address (esptool prints it too), not the Wi-Fi chip's. */
        uint8_t mac[6] = {0};
        esp_efuse_mac_get_default(mac);
        snprintf(mac_text, sizeof mac_text, "%02x:%02x:%02x:%02x:%02x:%02x", mac[0], mac[1], mac[2], mac[3],
                 mac[4], mac[5]);
    }
    return mac_text;
}

static int number(const cJSON *from, int otherwise)
{
    return cJSON_IsNumber(from) ? from->valueint : otherwise;
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
    if (cJSON_IsTrue(cJSON_GetObjectItem(root, "update"))) {
        ESP_LOGI(TAG, "the hub asks to update now");
        update_now(); /* Settings, Desk panels: Update now */
    }

    desk_clock_t next = {.present = true};
    desk_day_t day = {0};
    desk_board_t board = {0};
    /* Built here, then copied in under the lock; static (only this task parses)
     * and in PSRAM, as the calendar alone is about 2 kB. */
    EXT_RAM_BSS_ATTR static desk_train_t train;
    EXT_RAM_BSS_ATTR static desk_agenda_t agenda;
    memset(&train, 0, sizeof train);
    memset(&agenda, 0, sizeof agenda);
    const cJSON *offset = cJSON_GetObjectItem(time, "utc_offset");
    next.utc_offset = cJSON_IsNumber(offset) ? offset->valueint : 0;

    const cJSON *screen;
    cJSON_ArrayForEach(screen, cJSON_GetObjectItem(root, "screens"))
    {
        const cJSON *kind = cJSON_GetObjectItem(screen, "kind");
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "agenda") == 0) {
            parse_agenda(screen, &agenda);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "train") == 0) {
            parse_train(screen, &train);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "board") == 0) {
            board.listed = true;
            copy_string(board.mac, sizeof board.mac, cJSON_GetObjectItem(screen, "mac"));
            copy_string(board.title, sizeof board.title, cJSON_GetObjectItem(screen, "title"));
            copy_string(board.hint, sizeof board.hint, cJSON_GetObjectItem(screen, "hint"));
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "day") == 0) {
            day.present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
            day.stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
            copy_string(day.title, sizeof day.title, cJSON_GetObjectItem(screen, "title"));
            copy_string(day.lead, sizeof day.lead, cJSON_GetObjectItem(screen, "lead"));
            copy_string(day.rest, sizeof day.rest, cJSON_GetObjectItem(screen, "rest"));
            copy_string(day.sunrise, sizeof day.sunrise, cJSON_GetObjectItem(screen, "sunrise"));
            copy_string(day.sunset, sizeof day.sunset, cJSON_GetObjectItem(screen, "sunset"));
            copy_string(day.credit, sizeof day.credit, cJSON_GetObjectItem(screen, "credit"));
            day.high = number(cJSON_GetObjectItem(screen, "high"), 0);
            day.low = number(cJSON_GetObjectItem(screen, "low"), 0);
            day.sunrise_minute = number(cJSON_GetObjectItem(screen, "sunrise_minute"), -1);
            day.sunset_minute = number(cJSON_GetObjectItem(screen, "sunset_minute"), -1);
            day.today = cJSON_IsNumber(cJSON_GetObjectItem(screen, "now_minute"));
            const cJSON *t, *r = cJSON_GetObjectItem(screen, "rain");
            cJSON_ArrayForEach(t, cJSON_GetObjectItem(screen, "temperatures"))
            {
                if (day.count < DESK_DAY_POINTS && cJSON_IsNumber(t)) {
                    const cJSON *chance = cJSON_GetArrayItem(r, day.count);
                    day.rain[day.count] = number(chance, 0);
                    day.temperatures[day.count++] = (float)t->valuedouble;
                }
            }
            continue;
        }
        if (!cJSON_IsString(kind) || strcmp(kind->valuestring, "clock") != 0) {
            continue;
        }
        next.listed = true;
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
    day.version = day_state.version + 1;
    day_state = day;
    agenda.version = agenda_state.version + 1;
    agenda_state = agenda;
    train.version = train_state.version + 1;
    train_state = train;
    board.version = board_state.version + 1;
    board_state = board;
    xSemaphoreGive(lock);
}

static void desk_task(void *arg)
{
    char url[200];
    snprintf(url, sizeof url, "%s/api/desk/board/%s?firmware=%s", CONFIG_PANEL_HUB_URL, desk_mac(),
             esp_app_get_description()->version);
    char *body = malloc(BODY_MAX);
    for (;;) {
        if (net_state().connected && !update_busy()) {
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
                update_hub_answered();
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
