/* The Now panel's headlines screen (plan.md M20), as in the desk panels mockup:
 * the lead story full-bleed over its picture with its source as a badge, then
 * two more with square thumbnails. The stories come worded from the hub
 * (app/desk_headlines.py), the pictures from pictures.c. A tap on a story saves
 * it to Readeck (actions.c, with the board's device key): its bookmark fills at
 * once, and empties again when saving failed. A saved story stays saved. */

#include "screen_headlines.h"

#include <stdio.h>
#include <string.h>

#include "actions.h"
#include "desk.h"
#include "esp_attr.h"
#include "esp_heap_caps.h"
#include "lvgl.h"
#include "pictures.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define LEFT 40
#define WIDTH 640
#define LEAD_TOP 36
#define LEAD_HEIGHT 320
#define THUMB 112
#define ROW_TOP 390
#define ROW_HEIGHT 150

static lv_obj_t *lead, *lead_image, *badge, *lead_age, *lead_title;
static struct {
    lv_obj_t *row, *image, *placeholder, *kicker, *title;
} rows[2];
static lv_obj_t *marks[DESK_STORIES];  /* the bookmarks; their user data: filled or not */
static bool tapped[DESK_STORIES];      /* filled by a tap, until the hub says saved */
static picture_t showing[PICTURE_SLOTS];
static lv_image_dsc_t images[PICTURE_SLOTS];
EXT_RAM_BSS_ATTR static desk_headlines_t shown; /* off the LVGL task's small stack */

static lv_obj_t *plain(lv_obj_t *parent)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

static lv_obj_t *text(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(colour), 0);
    lv_label_set_text(label, "");
    return label;
}

/* The bookmark, as in the mockup: an outline, filled in violet once saved. */
static void draw_bookmark(lv_event_t *event)
{
    lv_obj_t *mark = lv_event_get_target(event);
    lv_layer_t *layer = lv_event_get_layer(event);
    lv_area_t at;
    lv_obj_get_coords(mark, &at);
    int x = at.x1 + 2, y = at.y1 + 2;
    if (lv_obj_get_user_data(mark)) {
        lv_color_t violet = lv_color_hex(0xb4a9ff);
        lv_draw_rect_dsc_t body;
        lv_draw_rect_dsc_init(&body);
        body.bg_color = violet;
        lv_area_t top = {x, y, x + 20, y + 20};
        lv_draw_rect(layer, &body, &top);
        lv_draw_triangle_dsc_t leg;
        lv_draw_triangle_dsc_init(&leg);
        leg.color = violet;
        leg.p[0] = (lv_point_precise_t){x, y + 20};
        leg.p[1] = (lv_point_precise_t){x, y + 28};
        leg.p[2] = (lv_point_precise_t){x + 10, y + 20};
        lv_draw_triangle(layer, &leg);
        leg.p[0] = (lv_point_precise_t){x + 20, y + 20};
        leg.p[1] = (lv_point_precise_t){x + 20, y + 28};
        lv_draw_triangle(layer, &leg);
        return;
    }
    const lv_point_precise_t shape[] = {{0, 0}, {20, 0}, {20, 28}, {10, 20}, {0, 28}, {0, 0}};
    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.color = lv_color_white();
    line.opa = 180;
    line.width = 3;
    line.round_start = line.round_end = 1;
    for (int i = 0; i < 5; i++) {
        line.p1 = (lv_point_precise_t){x + shape[i].x, y + shape[i].y};
        line.p2 = (lv_point_precise_t){x + shape[i + 1].x, y + shape[i + 1].y};
        lv_draw_line(layer, &line);
    }
}

static lv_obj_t *bookmark(lv_obj_t *parent, lv_align_t align, int x, int y)
{
    lv_obj_t *mark = plain(parent);
    lv_obj_set_size(mark, 26, 34);
    lv_obj_align(mark, align, x, y);
    lv_obj_add_event_cb(mark, draw_bookmark, LV_EVENT_DRAW_MAIN, NULL);
    return mark;
}

static void fill(int story, bool filled)
{
    if (marks[story] && (bool)lv_obj_get_user_data(marks[story]) != filled) {
        lv_obj_set_user_data(marks[story], (void *)filled);
        lv_obj_invalidate(marks[story]);
    }
}

/* A tap on a story: save it, unless it already is (removing happens in the hub). */
void screen_headlines_tap(int story)
{
    if (story < 0 || story >= shown.count || shown.stories[story].saved || tapped[story]) {
        return;
    }
    if (actions_save(shown.stories[story].id)) {
        tapped[story] = true;
        fill(story, true);
    }
}

static void on_tap(lv_event_t *event)
{
    screen_headlines_tap((int)(intptr_t)lv_event_get_user_data(event));
}

static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

/* Swap in a newer picture for a slot, then free the one it replaces. */
static void take_picture(int slot, lv_obj_t *image)
{
    picture_t fresh;
    if (!pictures_take(slot, &fresh)) {
        return;
    }
    picture_t old = showing[slot];
    showing[slot] = fresh;
    if (fresh.pixels) {
        images[slot] = (lv_image_dsc_t){
            .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = LV_COLOR_FORMAT_RGB888, .w = fresh.width,
                       .h = fresh.height, .stride = fresh.width * 3},
            .data_size = fresh.width * fresh.height * 3,
            .data = fresh.pixels,
        };
        lv_image_set_src(image, &images[slot]);
        lv_image_cache_drop(&images[slot]);
    } else {
        lv_image_set_src(image, NULL);
    }
    lv_obj_set_flag(image, LV_OBJ_FLAG_HIDDEN, fresh.pixels == NULL);
    heap_caps_free(old.pixels);
}

static void tick(lv_timer_t *timer)
{
    take_picture(0, lead_image);
    take_picture(1, rows[0].image);
    take_picture(2, rows[1].image);
    for (int i = 0; i < 2; i++) {
        lv_obj_set_flag(rows[i].placeholder, LV_OBJ_FLAG_HIDDEN, showing[i + 1].pixels != NULL);
    }

    /* A tap that failed empties its bookmark again. */
    for (int i = 0; i < shown.count; i++) {
        if (tapped[i] && actions_saved(shown.stories[i].id) == ACTION_FAILED) {
            tapped[i] = false;
            fill(i, shown.stories[i].saved);
        }
    }

    static uint32_t version;
    if (desk_headlines_version() == version) {
        return;
    }
    char before[DESK_STORIES][20];
    for (int i = 0; i < DESK_STORIES; i++) {
        snprintf(before[i], sizeof before[i], "%s", shown.stories[i].id);
    }
    shown = desk_headlines();
    version = shown.version;
    for (int i = 0; i < DESK_STORIES; i++) {
        if (strcmp(before[i], shown.stories[i].id) != 0) {
            tapped[i] = false; /* another story now */
        }
        if (tapped[i] && actions_saved(shown.stories[i].id) == ACTION_DONE && shown.stories[i].saved) {
            tapped[i] = false; /* the hub knows */
        }
        fill(i, shown.stories[i].saved || tapped[i]);
    }
    if (!shown.present || shown.count == 0) {
        return;
    }
    char caps[48];
    lv_label_set_text(badge, shown.stories[0].source);
    lv_label_set_text(lead_age, shown.stories[0].age);
    lv_label_set_text(lead_title, shown.stories[0].title);
    for (int i = 0; i < 2; i++) {
        bool there = shown.count > i + 1;
        lv_obj_set_flag(rows[i].row, LV_OBJ_FLAG_HIDDEN, !there);
        if (there) {
            char line[64];
            snprintf(line, sizeof line, "%s · %s", shown.stories[i + 1].source, shown.stories[i + 1].age);
            upper(caps, sizeof caps, line);
            lv_label_set_text(rows[i].kicker, caps);
            lv_label_set_text(rows[i].title, shown.stories[i + 1].title);
        }
    }
}

void screen_headlines_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* The lead: its picture with a dark fade under the title; a calm violet
     * gradient when it has none. */
    lead = plain(screen);
    lv_obj_set_pos(lead, LEFT, LEAD_TOP);
    lv_obj_set_size(lead, WIDTH, LEAD_HEIGHT);
    lv_obj_set_style_radius(lead, 24, 0);
    lv_obj_set_style_clip_corner(lead, true, 0);
    lv_obj_set_style_bg_opa(lead, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(lead, lv_color_hex(0x2a2550), 0);
    lv_obj_set_style_bg_grad_color(lead, lv_color_hex(0x121118), 0);
    lv_obj_set_style_bg_grad_dir(lead, LV_GRAD_DIR_VER, 0);
    lead_image = lv_image_create(lead);
    lv_obj_set_pos(lead_image, 0, 0);
    lv_obj_add_flag(lead_image, LV_OBJ_FLAG_HIDDEN);

    /* A softer fade at the top, so the badge, age and bookmark read on a bright picture. */
    lv_obj_t *shade = plain(lead);
    lv_obj_set_size(shade, WIDTH, 110);
    lv_obj_align(shade, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_opa(shade, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(shade, lv_color_black(), 0);
    lv_obj_set_style_bg_grad_color(shade, lv_color_black(), 0);
    lv_obj_set_style_bg_grad_dir(shade, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_main_opa(shade, 150, 0);
    lv_obj_set_style_bg_grad_opa(shade, 0, 0);

    lv_obj_t *fade = plain(lead);
    lv_obj_set_size(fade, WIDTH, 220);
    lv_obj_align(fade, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_opa(fade, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(fade, lv_color_black(), 0);
    lv_obj_set_style_bg_grad_color(fade, lv_color_black(), 0);
    lv_obj_set_style_bg_grad_dir(fade, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_main_opa(fade, 0, 0);
    lv_obj_set_style_bg_grad_opa(fade, 220, 0);

    /* The source as a badge, its age beside it, the bookmark on the right. */
    lv_obj_t *top = plain(lead);
    lv_obj_set_pos(top, 24, 22);
    lv_obj_set_size(top, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(top, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(top, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(top, 14, 0);
    badge = text(top, &instrument_28_bold, 0xf1eff7);
    lv_obj_set_style_bg_opa(badge, 150, 0);
    lv_obj_set_style_bg_color(badge, lv_color_hex(0x121118), 0);
    lv_obj_set_style_radius(badge, 18, 0);
    lv_obj_set_style_pad_hor(badge, 14, 0);
    lv_obj_set_style_pad_ver(badge, 4, 0);
    lead_age = text(top, &instrument_24, 0xe6e3ef);
    marks[0] = bookmark(lead, LV_ALIGN_TOP_RIGHT, -22, 20);
    lv_obj_add_flag(lead, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
    lv_obj_add_event_cb(lead, on_tap, LV_EVENT_CLICKED, (void *)0);

    lead_title = text(lead, &instrument_40, 0xffffff);
    lv_label_set_long_mode(lead_title, LV_LABEL_LONG_DOT);
    lv_obj_set_size(lead_title, WIDTH - 48, 3 * 48);
    lv_obj_set_style_text_line_space(lead_title, -2, 0);
    lv_obj_align(lead_title, LV_ALIGN_BOTTOM_LEFT, 24, -18);

    /* Two more, each with its thumbnail. */
    for (int i = 0; i < 2; i++) {
        lv_obj_t *row = rows[i].row = plain(screen);
        lv_obj_set_pos(row, LEFT, ROW_TOP + i * ROW_HEIGHT);
        lv_obj_set_size(row, WIDTH, THUMB);
        lv_obj_t *frame = plain(row);
        lv_obj_set_size(frame, THUMB, THUMB);
        lv_obj_set_style_radius(frame, 18, 0);
        lv_obj_set_style_clip_corner(frame, true, 0);
        rows[i].placeholder = plain(frame);
        lv_obj_set_size(rows[i].placeholder, THUMB, THUMB);
        lv_obj_set_style_bg_opa(rows[i].placeholder, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(rows[i].placeholder, lv_color_hex(0x2a2550), 0);
        lv_obj_set_style_bg_grad_color(rows[i].placeholder, lv_color_hex(0x16151c), 0);
        lv_obj_set_style_bg_grad_dir(rows[i].placeholder, LV_GRAD_DIR_VER, 0);
        rows[i].image = lv_image_create(frame);
        lv_obj_add_flag(rows[i].image, LV_OBJ_FLAG_HIDDEN);

        rows[i].kicker = text(row, &instrument_24, 0x8a8794);
        lv_obj_set_style_text_letter_space(rows[i].kicker, 2, 0);
        lv_obj_set_pos(rows[i].kicker, THUMB + 24, 0);
        rows[i].title = text(row, &instrument_28_bold, 0xf1eff7);
        lv_label_set_long_mode(rows[i].title, LV_LABEL_LONG_DOT);
        lv_obj_set_size(rows[i].title, WIDTH - THUMB - 24 - 56, 2 * 36);
        lv_obj_set_pos(rows[i].title, THUMB + 24, 34);
        marks[i + 1] = bookmark(row, LV_ALIGN_RIGHT_MID, -4, 0);
        lv_obj_add_flag(row, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_EVENT_BUBBLE);
        lv_obj_add_event_cb(row, on_tap, LV_EVENT_CLICKED, (void *)(intptr_t)(i + 1));
    }

    lv_timer_create(tick, 1000, NULL);
}
