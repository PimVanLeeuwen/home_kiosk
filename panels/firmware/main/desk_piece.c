/* The pieces from the hub's answer (desk_piece.h). Parsed on the hub task into `next`,
 * published under the lock in one go, copied out by the screens on the LVGL task. */

#include "desk_piece.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_attr.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static const char *NAMES[PIECES] = {"sky",   "night", "year", "week",    "radar",  "countdown",
                                     "art",   "photo", "orbit", "run", "runweek", "session",
                                     "streets"};
static const char *FONTS[] = {"24", "28", "40", "52", "clock", "digits"};

EXT_RAM_BSS_ATTR static desk_piece_t state[PIECES], next[PIECES];
static SemaphoreHandle_t lock;

const char *desk_piece_name(int which)
{
    return which >= 0 && which < PIECES ? NAMES[which] : "";
}

void desk_piece_begin(void)
{
    if (lock == NULL) {
        lock = xSemaphoreCreateMutex();
    }
    memset(next, 0, sizeof next);
}

static int number(const cJSON *item, const char *name, int fallback)
{
    const cJSON *value = cJSON_GetObjectItem(item, name);
    return cJSON_IsNumber(value) ? value->valueint : fallback;
}

static void label(const cJSON *item, piece_label_t *to)
{
    const cJSON *text = cJSON_GetObjectItem(item, "text");
    snprintf(to->text, sizeof to->text, "%s", cJSON_IsString(text) ? text->valuestring : "");
    to->x = (int16_t)number(item, "x", 36);
    to->y = (int16_t)number(item, "y", 36);
    to->width = (int16_t)number(item, "width", 648);
    to->lines = (uint8_t)number(item, "lines", 1);
    to->spacing = (uint8_t)number(item, "spacing", 0);
    const cJSON *font = cJSON_GetObjectItem(item, "font");
    to->font = 0;
    for (size_t i = 0; i < sizeof FONTS / sizeof FONTS[0]; i++) {
        if (cJSON_IsString(font) && strcmp(font->valuestring, FONTS[i]) == 0) {
            to->font = (uint8_t)i;
        }
    }
    const cJSON *align = cJSON_GetObjectItem(item, "align");
    to->align = !cJSON_IsString(align) ? PIECE_LEFT
                : strcmp(align->valuestring, "centre") == 0 ? PIECE_CENTRE
                : strcmp(align->valuestring, "right") == 0  ? PIECE_RIGHT
                                                            : PIECE_LEFT;
    const cJSON *colour = cJSON_GetObjectItem(item, "colour");
    to->colour = cJSON_IsString(colour) ? (uint32_t)strtoul(colour->valuestring, NULL, 16) : 0xffffff;
}

bool desk_piece_parse(const cJSON *screen)
{
    const cJSON *kind = cJSON_GetObjectItem(screen, "kind");
    if (!cJSON_IsString(kind)) {
        return false;
    }
    for (int i = 0; i < PIECES; i++) {
        if (strcmp(kind->valuestring, NAMES[i]) != 0) {
            continue;
        }
        desk_piece_t *p = &next[i];
        p->present = cJSON_IsTrue(cJSON_GetObjectItem(screen, "present"));
        p->stale = cJSON_IsTrue(cJSON_GetObjectItem(screen, "stale"));
        const cJSON *item;
        cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "labels"))
        {
            if (p->label_count < PIECE_LABELS) {
                label(item, &p->labels[p->label_count++]);
            }
        }
        cJSON_ArrayForEach(item, cJSON_GetObjectItem(screen, "path"))
        {
            const cJSON *x = cJSON_GetArrayItem(item, 0), *y = cJSON_GetArrayItem(item, 1);
            if (p->path_count < PIECE_PATH && cJSON_IsNumber(x) && cJSON_IsNumber(y)) {
                p->path[p->path_count][0] = (int16_t)x->valueint;
                p->path[p->path_count][1] = (int16_t)y->valueint;
                p->path_count++;
            }
        }
        const cJSON *clock = cJSON_GetObjectItem(screen, "clock");
        p->has_clock = cJSON_IsObject(clock);
        if (p->has_clock) {
            label(clock, &p->clock);
        }
        return true;
    }
    return false;
}

void desk_piece_commit(void)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    for (int i = 0; i < PIECES; i++) {
        next[i].version = state[i].version + 1;
        state[i] = next[i];
    }
    xSemaphoreGive(lock);
}

bool desk_has_piece(int which)
{
    if (lock == NULL || which < 0 || which >= PIECES) {
        return false;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    bool present = state[which].present;
    xSemaphoreGive(lock);
    return present;
}

uint32_t desk_piece_version(int which)
{
    if (lock == NULL || which < 0 || which >= PIECES) {
        return 0;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    uint32_t version = state[which].version;
    xSemaphoreGive(lock);
    return version;
}

void desk_piece_copy(int which, desk_piece_t *out)
{
    memset(out, 0, sizeof *out);
    if (lock == NULL || which < 0 || which >= PIECES) {
        return;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    *out = state[which];
    xSemaphoreGive(lock);
}
