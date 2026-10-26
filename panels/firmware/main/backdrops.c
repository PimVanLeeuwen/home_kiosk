/* Painted backgrounds (backdrops.h). The hub task fetches a background only when its
 * path changes and keeps the JPEG; the LVGL task decodes the one for the screen that
 * turns in, while the light is down, into whichever of two buffers the screen on display
 * does not use. A newer background for the screen on display is swapped in the same way
 * within a couple of seconds. Both buffers and the JPEGs live in PSRAM. */

#include "backdrops.h"

#include <stdio.h>
#include <string.h>

#include "driver/jpeg_decode.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "pictures.h"
#include "ui.h"

static const char *TAG = "backdrops";

#define KINDS 40 /* every screen kind the hub may send, and the screens that show one */
#define SIZE 720
#define MAX_JPEG (160 * 1024)
#define CHECK_MS 2000

typedef struct {
    char kind[16];
    char path[64];     /* what the hub last named */
    uint8_t *jpeg;     /* from jpeg_alloc_decoder_mem; NULL for none */
    size_t size;
    uint32_t version;  /* changes with every new JPEG (or none) */
} stored_t;

typedef struct {
    lv_obj_t *screen, *image;
    int kind;               /* in stored[] */
    uint32_t shown_version; /* what the image shows; 0 for nothing */
    int buffer;             /* which buffer the image shows, or -1 */
} screen_t;

EXT_RAM_BSS_ATTR static stored_t stored[KINDS];
EXT_RAM_BSS_ATTR static screen_t screens[KINDS];
static int kinds, attached;

#define DEPENDANTS 64
#define GLASS_OPA 175
EXT_RAM_BSS_ATTR static struct {
    lv_obj_t *obj;
    bool glass; /* else: steps aside */
} dependants[DEPENDANTS];
static int dependant_count;
static SemaphoreHandle_t lock;
static uint8_t *buffers[2];
static size_t rooms[2];
static lv_image_dsc_t dscs[2];

static int kind_index(const char *kind)
{
    for (int i = 0; i < kinds; i++) {
        if (strcmp(stored[i].kind, kind) == 0) {
            return i;
        }
    }
    if (kinds == KINDS) {
        return -1;
    }
    snprintf(stored[kinds].kind, sizeof stored[kinds].kind, "%s", kind);
    return kinds++;
}

static void ensure_lock(void)
{
    if (lock == NULL) {
        lock = xSemaphoreCreateMutex();
    }
}

void backdrops_want(const char *kind, const char *path)
{
    ensure_lock();
    xSemaphoreTake(lock, portMAX_DELAY);
    int k = kind_index(kind);
    bool same = k < 0 || strcmp(stored[k].path, path) == 0;
    xSemaphoreGive(lock);
    if (same) {
        return;
    }
    uint8_t *jpeg = NULL;
    size_t size = 0;
    if (path[0]) {
        jpeg_decode_memory_alloc_cfg_t in_cfg = {.buffer_direction = JPEG_DEC_ALLOC_INPUT_BUFFER};
        size_t room = 0;
        uint8_t *fetched = jpeg_alloc_decoder_mem(MAX_JPEG, &in_cfg, &room);
        if (fetched == NULL || !pictures_fetch(path, fetched, room, &size)) {
            heap_caps_free(fetched);
            ESP_LOGW(TAG, "%s: background not loaded", kind);
            return; /* tried again with the next answer */
        }
        /* Kept at its own size: a 160 kB buffer per screen would add up. */
        size_t kept_room = 0;
        jpeg = jpeg_alloc_decoder_mem(size, &in_cfg, &kept_room);
        if (jpeg) {
            memcpy(jpeg, fetched, size);
        }
        heap_caps_free(fetched);
        if (jpeg == NULL) {
            return;
        }
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    heap_caps_free(stored[k].jpeg);
    stored[k].jpeg = jpeg;
    stored[k].size = size;
    stored[k].version++;
    snprintf(stored[k].path, sizeof stored[k].path, "%s", path);
    xSemaphoreGive(lock);
}

void backdrops_aside(lv_obj_t *obj)
{
    if (dependant_count < DEPENDANTS) {
        dependants[dependant_count].obj = obj, dependants[dependant_count++].glass = false;
    }
}

void backdrops_glass(lv_obj_t *obj)
{
    if (dependant_count < DEPENDANTS) {
        dependants[dependant_count].obj = obj, dependants[dependant_count++].glass = true;
    }
}

/* The screen's own light and tiles, for whether it shows a painted background now. */
static void depend(lv_obj_t *screen, bool painted)
{
    for (int i = 0; i < dependant_count; i++) {
        if (lv_obj_get_screen(dependants[i].obj) != screen) {
            continue;
        }
        if (dependants[i].glass) {
            lv_obj_set_style_bg_opa(dependants[i].obj, painted ? GLASS_OPA : LV_OPA_COVER, 0);
        } else {
            lv_obj_set_flag(dependants[i].obj, LV_OBJ_FLAG_HIDDEN, painted);
        }
    }
}

static screen_t *find(const lv_obj_t *screen)
{
    for (int i = 0; i < attached; i++) {
        if (screens[i].screen == screen) {
            return &screens[i];
        }
    }
    return NULL;
}

/* Nothing on `s` any more (its buffer may be reused). */
static void clear(screen_t *s)
{
    lv_image_set_src(s->image, NULL);
    lv_obj_add_flag(s->image, LV_OBJ_FLAG_HIDDEN);
    depend(s->screen, false);
    s->buffer = -1;
    s->shown_version = 0;
}

static void show(screen_t *s)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    stored_t *k = &stored[s->kind];
    if (k->version == s->shown_version && (s->buffer >= 0 || k->jpeg == NULL)) {
        xSemaphoreGive(lock);
        return;
    }
    if (k->jpeg == NULL) {
        uint32_t version = k->version;
        xSemaphoreGive(lock);
        clear(s);
        s->shown_version = version;
        return;
    }
    /* The buffer the screen on display does not use (a turn: the outgoing screen). */
    screen_t *active = find(lv_screen_active());
    int b = (active && active->buffer == 0) ? 1 : 0;
    for (int i = 0; i < attached; i++) {
        if (screens[i].buffer == b && &screens[i] != s) {
            clear(&screens[i]);
        }
    }
    if (buffers[b] == NULL) {
        jpeg_decode_memory_alloc_cfg_t out_cfg = {.buffer_direction = JPEG_DEC_ALLOC_OUTPUT_BUFFER};
        buffers[b] = jpeg_alloc_decoder_mem(SIZE * SIZE * 3, &out_cfg, &rooms[b]);
    }
    int width = 0, height = 0;
    bool ok = buffers[b] && pictures_decode_into(k->jpeg, k->size, buffers[b], rooms[b], &width, &height) &&
              width == SIZE && height == SIZE;
    uint32_t version = k->version;
    xSemaphoreGive(lock);
    if (!ok) {
        ESP_LOGW(TAG, "%s: background not decoded", k->kind);
        return;
    }
    dscs[b] = (lv_image_dsc_t){
        .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_RGB888, .w = SIZE, .h = SIZE, .stride = SIZE * 3},
        .data_size = SIZE * SIZE * 3,
        .data = buffers[b],
    };
    lv_image_cache_drop(&dscs[b]);
    lv_image_set_src(s->image, &dscs[b]);
    lv_obj_remove_flag(s->image, LV_OBJ_FLAG_HIDDEN);
    depend(s->screen, true);
    s->buffer = b; /* its old buffer, if any, is free now */
    s->shown_version = version;
}

void backdrops_show(lv_obj_t *screen)
{
    screen_t *s = find(screen);
    if (s) {
        show(s);
    }
}

/* A newer background for the screen on display. */
static void check(lv_timer_t *timer)
{
    backdrops_show(lv_screen_active());
}

void backdrops_attach(lv_obj_t *screen, const char *kind)
{
    ensure_lock();
    if (attached == KINDS) {
        return;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    int k = kind_index(kind);
    xSemaphoreGive(lock);
    if (k < 0) {
        return;
    }
    lv_obj_t *image = lv_image_create(screen);
    lv_obj_remove_flag(image, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(image, 0, 0);
    lv_obj_add_flag(image, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_to_index(image, 0); /* under everything the screen draws */
    screens[attached++] = (screen_t){.screen = screen, .image = image, .kind = k, .buffer = -1};
    if (attached == 1) {
        lv_timer_create(check, CHECK_MS, NULL);
    }
}
