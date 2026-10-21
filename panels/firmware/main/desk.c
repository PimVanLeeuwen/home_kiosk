/* The hub's answer for this board: GET /api/desk/board/<MAC>?firmware=<version>
 * every 30 s; the hub knows which panel the board is. It also
 * carries the hub's time, so the panel never contacts the internet: the clock
 * is set from it whenever it is off by more than a second. */

#include "desk.h"
#include "desk_pipelines.h"
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
#include "nvs.h"
#include "pictures.h"
#include "update.h"
#include "sdkconfig.h"

static const char *TAG = "desk";
/* The hub's latest answer, in PSRAM: internal RAM is for the Wi-Fi buffers. */
EXT_RAM_BSS_ATTR static desk_clock_t clock_state;
EXT_RAM_BSS_ATTR static desk_day_t day_state;
EXT_RAM_BSS_ATTR static desk_board_t board_state;
EXT_RAM_BSS_ATTR static desk_train_t train_state;
EXT_RAM_BSS_ATTR static desk_agenda_t agenda_state;
EXT_RAM_BSS_ATTR static desk_headlines_t headlines_state;
EXT_RAM_BSS_ATTR static desk_lights_t lights_state;
EXT_RAM_BSS_ATTR static desk_playing_t playing_state;
EXT_RAM_BSS_ATTR static desk_music_t music_state;
EXT_RAM_BSS_ATTR static desk_laundry_t laundry_state;
EXT_RAM_BSS_ATTR static desk_air_t air_state;
EXT_RAM_BSS_ATTR static desk_pipeline_t pipeline_state;
EXT_RAM_BSS_ATTR static desk_pipelines_t pipelines_state;
EXT_RAM_BSS_ATTR static desk_apple_t apple_state;
static TaskHandle_t desk_task_handle;
static volatile bool rotates = true;
static char mac_text[18];
static volatile bool dimmed; /* the hub's "dim": the living room lights are all off */
static char key[64]; /* the device key, from the board's storage (NVS "desk") */
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
static uint32_t colour(const cJSON *from);

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

bool desk_dim(void)
{
    return dimmed;
}

bool desk_rotates(void)
{
    return rotates;
}

void desk_poll_now(void)
{
    if (desk_task_handle) {
        xTaskNotifyGive(desk_task_handle);
    }
}

bool desk_has_lights(void)
{
    return has(&lights_state.present);
}

uint32_t desk_lights_version(void)
{
    if (lock == NULL) {
        return 0;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    uint32_t version = lights_state.version;
    xSemaphoreGive(lock);
    return version;
}

desk_lights_t desk_lights(void)
{
    desk_lights_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = lights_state;
    xSemaphoreGive(lock);
    return copy;
}

#define GETTERS(kind, type, state)                         \
    bool desk_has_##kind(void)                             \
    {                                                      \
        return has(&state.present);                        \
    }                                                      \
    uint32_t desk_##kind##_version(void)                   \
    {                                                      \
        if (lock == NULL) {                                \
            return 0;                                      \
        }                                                  \
        xSemaphoreTake(lock, portMAX_DELAY);               \
        uint32_t version = state.version;                  \
        xSemaphoreGive(lock);                              \
        return version;                                    \
    }                                                      \
    type desk_##kind(void)                                 \
    {                                                      \
        type copy = {0};                                   \
        if (lock == NULL) {                                \
            return copy;                                   \
        }                                                  \
        xSemaphoreTake(lock, portMAX_DELAY);               \
        copy = state;                                      \
        xSemaphoreGive(lock);                              \
        return copy;                                       \
    }

GETTERS(playing, desk_playing_t, playing_state)
GETTERS(music, desk_music_t, music_state)
GETTERS(laundry, desk_laundry_t, laundry_state)
GETTERS(air, desk_air_t, air_state)

/* As GETTERS, but copying into the caller's buffer: for states too big for a stack. */
#define COPIERS(kind, type, state)                         \
    bool desk_has_##kind(void)                             \
    {                                                      \
        return has(&state.present);                        \
    }                                                      \
    uint32_t desk_##kind##_version(void)                   \
    {                                                      \
        if (lock == NULL) {                                \
            return 0;                                      \
        }                                                  \
        xSemaphoreTake(lock, portMAX_DELAY);               \
        uint32_t version = state.version;                  \
        xSemaphoreGive(lock);                              \
        return version;                                    \
    }                                                      \
    void desk_##kind##_copy(type *into)                    \
    {                                                      \
        if (lock == NULL) {                                \
            memset(into, 0, sizeof *into);                 \
            return;                                        \
        }                                                  \
        xSemaphoreTake(lock, portMAX_DELAY);               \
        *into = state;                                     \
        xSemaphoreGive(lock);                              \
    }

COPIERS(pipeline, desk_pipeline_t, pipeline_state)
COPIERS(pipelines, desk_pipelines_t, pipelines_state)
GETTERS(apple, desk_apple_t, apple_state)

static void parse_apple(const cJSON *screen, desk_apple_t *apple)
{
    apple->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    apple->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!apple->present) {
        return;
    }
    copy_string(apple->headline, sizeof apple->headline, cJSON_GetObjectItem(screen, "headline"));
    apple->headline_colour = colour(cJSON_GetObjectItem(screen, "headline_colour"));
    const cJSON *item;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "rooms"))
    {
        if (apple->count == 3) {
            break;
        }
        typeof(apple->rooms[0]) *room = &apple->rooms[apple->count++];
        copy_string(room->name, sizeof room->name, cJSON_GetObjectItem(item, "name"));
        const cJSON *glow = cJSON_GetObjectItem(item, "glow");
        room->glow = cJSON_IsString(glow) ? colour(glow) : 0;
        const cJSON *device;
        cJSON_ArrayForEach(device, cJSON_GetObjectItem(item, "devices"))
        {
            if (room->devices == 4) {
                break;
            }
            copy_string(room->device[room->devices].kind, sizeof room->device[0].kind,
                        cJSON_GetObjectItem(device, "kind"));
            room->device[room->devices++].online = cJSON_IsTrue(cJSON_GetObjectItem(device, "online"));
        }
    }
    const cJSON *playing = cJSON_GetObjectItem(screen, "playing");
    apple->has_playing = cJSON_IsObject(playing);
    if (apple->has_playing) {
        copy_string(apple->title, sizeof apple->title, cJSON_GetObjectItem(playing, "title"));
        copy_string(apple->where, sizeof apple->where, cJSON_GetObjectItem(playing, "where"));
        apple->playing_colour = colour(cJSON_GetObjectItem(playing, "colour"));
    }
}

static void parse_air(const cJSON *screen, desk_air_t *air)
{
    air->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    air->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!air->present) {
        return;
    }
    copy_string(air->room, sizeof air->room, cJSON_GetObjectItem(screen, "room"));
    copy_string(air->outside, sizeof air->outside, cJSON_GetObjectItem(screen, "outside"));
    copy_string(air->temperature, sizeof air->temperature, cJSON_GetObjectItem(screen, "temperature"));
    copy_string(air->humidity, sizeof air->humidity, cJSON_GetObjectItem(screen, "humidity"));
    copy_string(air->pm25, sizeof air->pm25, cJSON_GetObjectItem(screen, "pm25"));
    copy_string(air->quality, sizeof air->quality, cJSON_GetObjectItem(screen, "quality"));
    copy_string(air->word, sizeof air->word, cJSON_GetObjectItem(screen, "word"));
    air->colour = colour(cJSON_GetObjectItem(screen, "colour"));
    const cJSON *co2 = cJSON_GetObjectItem(screen, "co2");
    air->has_co2 = cJSON_IsNumber(co2);
    air->co2 = air->has_co2 ? co2->valueint : 0;
    air->ring = number(cJSON_GetObjectItem(screen, "ring"), 0);
    const cJSON *value;
    cJSON_ArrayForEach(value, cJSON_GetObjectItem(screen, "history"))
    {
        if (air->history_count < DESK_AIR_HISTORY && cJSON_IsNumber(value)) {
            air->history[air->history_count++] = (int16_t)value->valueint;
        }
    }
}

static void parse_laundry(const cJSON *screen, desk_laundry_t *laundry)
{
    laundry->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    laundry->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!laundry->present) {
        return;
    }
    copy_string(laundry->headline, sizeof laundry->headline, cJSON_GetObjectItem(screen, "headline"));
    laundry->headline_colour = colour(cJSON_GetObjectItem(screen, "headline_colour"));
    const cJSON *item;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "machines"))
    {
        if (laundry->count == 2) {
            break;
        }
        typeof(laundry->machines[0]) *m = &laundry->machines[laundry->count++];
        copy_string(m->name, sizeof m->name, cJSON_GetObjectItem(item, "name"));
        copy_string(m->state, sizeof m->state, cJSON_GetObjectItem(item, "state"));
        copy_string(m->line, sizeof m->line, cJSON_GetObjectItem(item, "line"));
        copy_string(m->status, sizeof m->status, cJSON_GetObjectItem(item, "status"));
        m->colour = colour(cJSON_GetObjectItem(item, "colour"));
        m->water = colour(cJSON_GetObjectItem(item, "water"));
        m->status_colour = colour(cJSON_GetObjectItem(item, "status_colour"));
        m->progress = number(cJSON_GetObjectItem(item, "progress"), 0);
        m->minutes = number(cJSON_GetObjectItem(item, "minutes"), -1);
    }
}

/* Also asks pictures.c for the cover: fetched only when it changed. */
static void parse_playing(const cJSON *screen, desk_playing_t *now)
{
    now->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    now->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    const cJSON *cover = cJSON_GetObjectItem(screen, "cover");
    now->has_cover = now->present && cJSON_IsString(cover);
    pictures_want(PICTURE_PLAYING, now->has_cover ? cover->valuestring : "");
    if (!now->present) {
        return;
    }
    copy_string(now->title, sizeof now->title, cJSON_GetObjectItem(screen, "title"));
    copy_string(now->subtitle, sizeof now->subtitle, cJSON_GetObjectItem(screen, "subtitle"));
    copy_string(now->device, sizeof now->device, cJSON_GetObjectItem(screen, "device"));
    now->colour = colour(cJSON_GetObjectItem(screen, "colour"));
    now->playing = cJSON_IsTrue(cJSON_GetObjectItem(screen, "playing"));
    const cJSON *value = cJSON_GetObjectItem(screen, "progress_ms");
    now->progress_ms = cJSON_IsNumber(value) ? (int64_t)value->valuedouble : 0;
    value = cJSON_GetObjectItem(screen, "duration_ms");
    now->duration_ms = cJSON_IsNumber(value) ? (int64_t)value->valuedouble : 0;
    value = cJSON_GetObjectItem(screen, "at");
    now->at = cJSON_IsNumber(value) ? value->valuedouble : 0;
}

static void parse_music(const cJSON *screen, desk_music_t *music)
{
    music->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    music->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    const cJSON *item;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "favourites"))
    {
        if (music->count == DESK_FAVOURITES) {
            break;
        }
        int i = music->count++;
        music->favourites[i].position = number(cJSON_GetObjectItem(item, "position"), i);
        copy_string(music->favourites[i].name, sizeof music->favourites[i].name, cJSON_GetObjectItem(item, "name"));
        music->favourites[i].colour = colour(cJSON_GetObjectItem(item, "colour"));
        const cJSON *cover = cJSON_GetObjectItem(item, "cover");
        music->favourites[i].has_cover = cJSON_IsString(cover);
        pictures_want(PICTURE_FAVOURITE + i, cJSON_IsString(cover) ? cover->valuestring : "");
    }
    for (int i = music->count; i < DESK_FAVOURITES; i++) {
        pictures_want(PICTURE_FAVOURITE + i, "");
    }
    copy_string(music->device, sizeof music->device, cJSON_GetObjectItem(screen, "device"));
    copy_string(music->last, sizeof music->last, cJSON_GetObjectItem(screen, "last"));
}

static void parse_lights(const cJSON *screen, desk_lights_t *lights)
{
    lights->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    lights->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    if (!lights->present) {
        return;
    }
    copy_string(lights->title, sizeof lights->title, cJSON_GetObjectItem(screen, "title"));
    copy_string(lights->count, sizeof lights->count, cJSON_GetObjectItem(screen, "count"));
    lights->any_on = cJSON_IsTrue(cJSON_GetObjectItem(screen, "any_on"));
    const cJSON *item;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "groups"))
    {
        if (lights->group_count == DESK_LIGHT_GROUPS) {
            break;
        }
        typeof(lights->groups[0]) *g = &lights->groups[lights->group_count++];
        copy_string(g->id, sizeof g->id, cJSON_GetObjectItem(item, "id"));
        copy_string(g->name, sizeof g->name, cJSON_GetObjectItem(item, "name"));
        copy_string(g->line, sizeof g->line, cJSON_GetObjectItem(item, "line"));
        g->on = cJSON_IsTrue(cJSON_GetObjectItem(item, "on"));
        g->brightness = number(cJSON_GetObjectItem(item, "brightness"), 0);
        g->tone = colour(cJSON_GetObjectItem(item, "tone"));
    }
    const cJSON *whites = cJSON_GetObjectItem(screen, "whites");
    if ((lights->has_whites = cJSON_IsObject(whites))) {
        copy_string(lights->whites_group, sizeof lights->whites_group, cJSON_GetObjectItem(whites, "group"));
        copy_string(lights->whites_name, sizeof lights->whites_name, cJSON_GetObjectItem(whites, "name"));
        lights->whites_kelvin = number(cJSON_GetObjectItem(whites, "kelvin"), 0);
        cJSON_ArrayForEach(item, cJSON_GetObjectItem(whites, "choices"))
        {
            if (lights->choice_count == DESK_WHITES) {
                break;
            }
            lights->choices[lights->choice_count].kelvin = number(cJSON_GetObjectItem(item, "kelvin"), 0);
            lights->choices[lights->choice_count++].tone = colour(cJSON_GetObjectItem(item, "tone"));
        }
    }
}

void desk_take_lights(const char *json)
{
    cJSON *root = cJSON_Parse(json);
    if (root == NULL) {
        return;
    }
    EXT_RAM_BSS_ATTR static desk_lights_t fresh;
    memset(&fresh, 0, sizeof fresh);
    parse_lights(root, &fresh);
    cJSON_Delete(root);
    xSemaphoreTake(lock, portMAX_DELAY);
    fresh.version = lights_state.version + 1;
    lights_state = fresh;
    xSemaphoreGive(lock);
}

bool desk_has_headlines(void)
{
    return has(&headlines_state.present);
}

desk_headlines_t desk_headlines(void)
{
    desk_headlines_t copy = {0};
    if (lock == NULL) {
        return copy;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = headlines_state;
    xSemaphoreGive(lock);
    return copy;
}

uint32_t desk_headlines_version(void)
{
    if (lock == NULL) {
        return 0;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    uint32_t version = headlines_state.version;
    xSemaphoreGive(lock);
    return version;
}

void desk_key(char *into, size_t size)
{
    if (lock == NULL) {
        into[0] = '\0';
        return;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    snprintf(into, size, "%s", key);
    xSemaphoreGive(lock);
}

/* The hub hands a board its key once: keep it, in memory and in the storage
 * that survives restarts and updates. Never logged. */
static void keep_key(const char *handed)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    snprintf(key, sizeof key, "%s", handed);
    xSemaphoreGive(lock);
    nvs_handle_t nvs;
    if (nvs_open("desk", NVS_READWRITE, &nvs) == ESP_OK) {
        nvs_set_str(nvs, "key", handed);
        nvs_commit(nvs);
        nvs_close(nvs);
    }
    ESP_LOGI(TAG, "device key received and kept");
}

static void load_key(void)
{
    nvs_handle_t nvs;
    size_t size = sizeof key;
    if (nvs_open("desk", NVS_READONLY, &nvs) == ESP_OK) {
        if (nvs_get_str(nvs, "key", key, &size) != ESP_OK) {
            key[0] = '\0';
        }
        nvs_close(nvs);
    }
}

/* Also asks pictures.c for each story's picture: fetched only when it changed. */
static void parse_headlines(const cJSON *screen, desk_headlines_t *news)
{
    news->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
    news->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
    const cJSON *item;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "stories"))
    {
        if (news->count == DESK_STORIES) {
            break;
        }
        int i = news->count++;
        copy_string(news->stories[i].id, sizeof news->stories[i].id, cJSON_GetObjectItem(item, "id"));
        news->stories[i].saved = cJSON_IsTrue(cJSON_GetObjectItem(item, "saved"));
        copy_string(news->stories[i].title, sizeof news->stories[i].title, cJSON_GetObjectItem(item, "title"));
        copy_string(news->stories[i].source, sizeof news->stories[i].source, cJSON_GetObjectItem(item, "source"));
        copy_string(news->stories[i].age, sizeof news->stories[i].age, cJSON_GetObjectItem(item, "age"));
        const cJSON *picture = cJSON_GetObjectItem(item, "picture");
        news->stories[i].has_picture = cJSON_IsString(picture);
        pictures_want(i, cJSON_IsString(picture) ? picture->valuestring : "");
    }
    for (int i = news->count; i < DESK_STORIES; i++) {
        pictures_want(i, "");
    }
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
    dimmed = cJSON_IsTrue(cJSON_GetObjectItem(root, "dim"));
    rotates = !cJSON_IsFalse(cJSON_GetObjectItem(root, "rotate"));
    const cJSON *handed = cJSON_GetObjectItem(root, "key");
    if (cJSON_IsString(handed) && handed->valuestring[0]) {
        keep_key(handed->valuestring);
    }
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
    EXT_RAM_BSS_ATTR static desk_headlines_t news;
    EXT_RAM_BSS_ATTR static desk_lights_t lights;
    EXT_RAM_BSS_ATTR static desk_playing_t playing;
    EXT_RAM_BSS_ATTR static desk_music_t music;
    EXT_RAM_BSS_ATTR static desk_laundry_t laundry;
    EXT_RAM_BSS_ATTR static desk_air_t air;
    EXT_RAM_BSS_ATTR static desk_pipeline_t pipeline;
    EXT_RAM_BSS_ATTR static desk_pipelines_t pipes;
    EXT_RAM_BSS_ATTR static desk_apple_t apple;
    memset(&train, 0, sizeof train);
    memset(&agenda, 0, sizeof agenda);
    memset(&news, 0, sizeof news);
    memset(&lights, 0, sizeof lights);
    memset(&playing, 0, sizeof playing);
    memset(&music, 0, sizeof music);
    memset(&laundry, 0, sizeof laundry);
    memset(&air, 0, sizeof air);
    memset(&pipeline, 0, sizeof pipeline);
    memset(&pipes, 0, sizeof pipes);
    memset(&apple, 0, sizeof apple);
    const cJSON *offset = cJSON_GetObjectItem(time, "utc_offset");
    next.utc_offset = cJSON_IsNumber(offset) ? offset->valueint : 0;

    const cJSON *screen;
    cJSON_ArrayForEach(screen, cJSON_GetObjectItem(root, "screens"))
    {
        const cJSON *kind = cJSON_GetObjectItem(screen, "kind");
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "playing") == 0) {
            parse_playing(screen, &playing);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "laundry") == 0) {
            parse_laundry(screen, &laundry);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "air") == 0) {
            parse_air(screen, &air);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "pipeline") == 0) {
            desk_parse_run(screen, &pipeline);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "pipelines") == 0) {
            desk_parse_pipelines(screen, &pipes);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "apple") == 0) {
            parse_apple(screen, &apple);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "music") == 0) {
            parse_music(screen, &music);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "lights") == 0) {
            parse_lights(screen, &lights);
            continue;
        }
        if (cJSON_IsString(kind) && strcmp(kind->valuestring, "headlines") == 0) {
            parse_headlines(screen, &news);
            continue;
        }
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
        copy_string(next.sun, sizeof next.sun, cJSON_GetObjectItem(screen, "sun"));
        const cJSON *sky = cJSON_GetObjectItem(screen, "sky");
        const cJSON *sky_colour = cJSON_GetObjectItem(sky, "colour");
        next.has_sky = cJSON_IsString(sky_colour);
        next.sky_colour = next.has_sky ? (uint32_t)strtoul(sky_colour->valuestring, NULL, 16) : 0;
        next.sky_opacity = (uint8_t)number(cJSON_GetObjectItem(sky, "opacity"), 90);
        for (int i = 0; i < 3; i++) {
            copy_string(next.rain_axis[i], sizeof next.rain_axis[i],
                        cJSON_GetArrayItem(cJSON_GetObjectItem(screen, "rain_axis"), i));
        }
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
    playing.version = playing_state.version + 1;
    playing_state = playing;
    laundry.version = laundry_state.version + 1;
    laundry_state = laundry;
    air.version = air_state.version + 1;
    air_state = air;
    pipeline.version = pipeline_state.version + 1;
    pipeline_state = pipeline;
    pipes.version = pipelines_state.version + 1;
    pipelines_state = pipes;
    apple.version = apple_state.version + 1;
    apple_state = apple;
    music.version = music_state.version + 1;
    music_state = music;
    lights.version = lights_state.version + 1;
    lights_state = lights;
    news.version = headlines_state.version + 1;
    headlines_state = news;
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
            /* The key it holds, so the hub knows the handover arrived (app/desk_keys.py);
             * until then the hub keeps sending it. */
            char held[64], auth[80];
            desk_key(held, sizeof held);
            if (held[0] != '\0') {
                snprintf(auth, sizeof auth, "Bearer %s", held);
                esp_http_client_set_header(client, "Authorization", auth);
            }
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
        /* Soon after Wi-Fi comes up, then every 30 s, or at once when asked
         * (desk_poll_now, after a change from the panel). */
        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(desk_clock().present ? EVERY_MS : 3000));
    }
}

void desk_start(void)
{
    lock = xSemaphoreCreateMutex();
    load_key();
    xTaskCreate(desk_task, "desk", 8192, NULL, 4, &desk_task_handle);
}
