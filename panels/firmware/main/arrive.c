/* Arrival motion (arrive.h). Cheap on purpose: a sweep and a count change one value per
 * frame, and a chart draws in by widening the box that clips it, so nothing is redrawn
 * into a canvas while it moves. */

#include "arrive.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_attr.h"
#include "ui.h"

#define PARTS 48
#define MOVE_MS 700
#define STAGGER_MS 90 /* between one screen's charts, in the order they were made; a ring and
                       * its number move together */

typedef enum { SWEEP, COUNT, DRAW_IN, REDRAW } kind_t;

typedef struct {
    lv_obj_t *obj;
    kind_t kind;
    int32_t full;  /* DRAW_IN: the width; SWEEP: the value to reach; REDRAW: how far, 0 to 1000 */
    int32_t wrote; /* the value this module last wrote, to notice the screen's own */
    /* COUNT: the label's words around its number, and how it writes it */
    char before[16], after[24];
    int decimals;
    char point;
    float target;
    char last[72]; /* the text last written */
} part_t;

EXT_RAM_BSS_ATTR static part_t parts[PARTS]; /* in PSRAM: internal RAM is scarce */
static int count;

static part_t *add(lv_obj_t *obj, kind_t kind)
{
    if (count == PARTS) {
        return NULL;
    }
    parts[count] = (part_t){.obj = obj, .kind = kind};
    return &parts[count++];
}

void arrive_sweep(lv_obj_t *obj)
{
    add(obj, SWEEP);
}

void arrive_count(lv_obj_t *label)
{
    add(label, COUNT);
}

void arrive_draw_in(lv_obj_t *obj, int32_t width, int32_t height)
{
    lv_obj_t *parent = lv_obj_get_parent(obj);
    lv_obj_t *box = ui_plain(parent);
    lv_obj_set_pos(box, lv_obj_get_style_x(obj, 0), lv_obj_get_style_y(obj, 0));
    lv_obj_set_size(box, width, height);
    lv_obj_move_to_index(box, lv_obj_get_index(obj)); /* where the chart was among its siblings */
    lv_obj_set_parent(obj, box);
    lv_obj_set_pos(obj, 0, 0);
    part_t *part = add(box, DRAW_IN);
    if (part) {
        part->full = width;
    }
}

void arrive_redraw(lv_obj_t *obj)
{
    part_t *part = add(obj, REDRAW);
    if (part) {
        part->full = 1000;
    }
}

int32_t arrive_share(const lv_obj_t *obj)
{
    for (int i = 0; i < count; i++) {
        if (parts[i].obj == obj && parts[i].kind == REDRAW) {
            return parts[i].full;
        }
    }
    return 1000;
}

static int32_t value_of(lv_obj_t *obj)
{
    return lv_obj_check_type(obj, &lv_arc_class) ? lv_arc_get_value(obj) : lv_bar_get_value(obj);
}

static void set_value(lv_obj_t *obj, int32_t value)
{
    if (lv_obj_check_type(obj, &lv_arc_class)) {
        lv_arc_set_value(obj, value);
    } else {
        lv_bar_set_value(obj, value, LV_ANIM_OFF);
    }
}

/* "+29.3%" as "+", 29.3 with one decimal and '.', "%"; false without a number. */
static bool split(const char *text, part_t *part)
{
    const char *start = text;
    while (*start && !(*start >= '0' && *start <= '9')) {
        start++;
    }
    if (!*start || (size_t)(start - text) >= sizeof part->before) {
        return false;
    }
    const char *end = start;
    while ((*end >= '0' && *end <= '9') || ((*end == '.' || *end == ',') && end[1] >= '0' && end[1] <= '9')) {
        end++;
    }
    if (strlen(end) >= sizeof part->after) {
        return false;
    }
    memcpy(part->before, text, start - text);
    part->before[start - text] = '\0';
    strcpy(part->after, end);
    part->point = '\0';
    part->decimals = 0;
    for (const char *c = start; c < end; c++) {
        if (*c == '.' || *c == ',') {
            part->point = *c;
            part->decimals = (int)(end - c - 1);
        }
    }
    char number[24];
    size_t n = (size_t)(end - start) < sizeof number - 1 ? (size_t)(end - start) : sizeof number - 1;
    memcpy(number, start, n);
    number[n] = '\0';
    for (char *c = number; *c; c++) {
        if (*c == ',') {
            *c = '.';
        }
    }
    part->target = strtof(number, NULL);
    return part->decimals <= 2;
}

static void write_count(part_t *part, float value)
{
    char number[24];
    snprintf(number, sizeof number, "%.*f", part->decimals, value);
    if (part->point == ',') {
        char *dot = strchr(number, '.');
        if (dot) {
            *dot = ',';
        }
    }
    snprintf(part->last, sizeof part->last, "%s%s%s", part->before, number, part->after);
    lv_label_set_text(part->obj, part->last);
}

static void step(void *var, int32_t at) /* at: 0 to 1000 along the move */
{
    part_t *part = var;
    switch (part->kind) {
    case DRAW_IN:
        lv_obj_set_width(part->obj, part->full * at / 1000);
        break;
    case REDRAW:
        part->full = at;
        lv_obj_invalidate(part->obj);
        break;
    case SWEEP:
        if (value_of(part->obj) != part->wrote) {
            lv_anim_delete(part, step); /* the screen set a new value: keep it */
            return;
        }
        part->wrote = part->full * at / 1000;
        set_value(part->obj, part->wrote);
        break;
    case COUNT:
        if (strcmp(lv_label_get_text(part->obj), part->last) != 0) {
            lv_anim_delete(part, step); /* the screen wrote a new number: keep it */
            return;
        }
        write_count(part, part->target * at / 1000);
        break;
    }
}

static void begin(part_t *part, uint32_t delay)
{
    switch (part->kind) {
    case DRAW_IN:
        lv_obj_set_width(part->obj, 0);
        break;
    case REDRAW:
        part->full = 0;
        lv_obj_invalidate(part->obj);
        break;
    case SWEEP:
        part->full = value_of(part->obj);
        part->wrote = 0;
        set_value(part->obj, 0);
        break;
    case COUNT:
        if (!split(lv_label_get_text(part->obj), part)) {
            return;
        }
        write_count(part, 0);
        break;
    }
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, part);
    lv_anim_set_exec_cb(&anim, step);
    lv_anim_set_values(&anim, 0, 1000);
    lv_anim_set_duration(&anim, MOVE_MS);
    lv_anim_set_delay(&anim, delay);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_out);
    lv_anim_start(&anim);
}

void arrive_begin(lv_obj_t *screen)
{
    uint32_t delay = 0;
    for (int i = 0; i < count; i++) {
        part_t *part = &parts[i];
        if (lv_obj_get_screen(part->obj) != screen || lv_obj_has_flag(part->obj, LV_OBJ_FLAG_HIDDEN)) {
            continue;
        }
        lv_anim_delete(part, step);
        begin(part, part->kind == DRAW_IN ? delay : 0);
        if (part->kind == DRAW_IN) {
            delay += STAGGER_MS;
        }
    }
}
