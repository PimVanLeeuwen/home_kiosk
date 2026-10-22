/* The House panel's Services screen (plan.md M20, the ring as planned): the outside
 * services the house uses. While all is well their logos sit in a ring around a
 * glowing check, each on a dark tile with a glow in its brand colour; during an
 * incident the worst one becomes a card (what, how long, its last steps) with the
 * others small below. Words from the hub (app/desk_services.py); logos from
 * images/logos.c, a letter for a service without one. */

#include "screen_services.h"

#include <math.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "images/logos.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);
LV_IMAGE_DECLARE(glow_round);

#define LEFT 36
#define CX 360
#define CY 400
#define RADIUS 210
#define BIG 88   /* a tile in the ring */
#define CARD_TILE 72
#define SMALL 64 /* a tile below the incident card */
#define SMALL_Y 512

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define RED 0xff6b6b
#define VIOLET 0x8f80ff
#define GREY 0x8a8794

typedef struct {
    lv_obj_t *box, *logo, *letter;
} tile_t;

static lv_obj_t *sky, *title, *pill, *pill_text;
static lv_obj_t *ring_view, *names[DESK_SERVICES];
static tile_t ring[DESK_SERVICES];
static lv_obj_t *incident_view, *card, *card_name, *card_line, *card_title, *steps[DESK_SERVICE_STEPS],
    *step_dots[DESK_SERVICE_STEPS], *step_times[DESK_SERVICE_STEPS], *step_rows[DESK_SERVICE_STEPS], *others;
static tile_t card_tile, small[DESK_SERVICES];
EXT_RAM_BSS_ATTR static desk_services_t shown; /* off the LVGL task's small stack */

static uint32_t tone_colour(char tone)
{
    return tone == 'o' ? RED : tone == 'd' ? AMBER : tone == 'm' ? VIOLET : GREEN;
}

/* A dark glass tile for a logo, with room for a letter when there is none. */
static tile_t tile_create(lv_obj_t *parent, int size)
{
    tile_t t;
    t.box = ui_plain(parent);
    lv_obj_set_size(t.box, size, size);
    lv_obj_set_style_radius(t.box, size * 28 / 100, 0);
    lv_obj_set_style_bg_color(t.box, lv_color_hex(0x101014), 0);
    lv_obj_set_style_bg_opa(t.box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(t.box, lv_color_hex(0x24242c), 0);
    lv_obj_set_style_border_width(t.box, 1, 0);
    lv_obj_set_style_shadow_width(t.box, size / 2, 0);
    lv_obj_set_style_shadow_opa(t.box, 70, 0);
    t.logo = lv_image_create(t.box);
    lv_image_set_scale(t.logo, 256 * size / 2 / 48);
    lv_obj_set_style_image_recolor_opa(t.logo, LV_OPA_COVER, 0);
    lv_obj_center(t.logo);
    t.letter = ui_text(t.box, &instrument_28_bold, 0xf1eff7);
    lv_obj_center(t.letter);
    return t;
}

static void tile_set(tile_t *t, const char *key, const char *name, bool dim)
{
    const logo_t *logo = LOGOS;
    while (logo->key != NULL && strcmp(logo->key, key) != 0) {
        logo++;
    }
    uint32_t glow = logo->key != NULL ? logo->glow : 0x4fa3ff;
    lv_obj_set_style_shadow_color(t->box, lv_color_hex(glow), 0);
    lv_obj_set_style_opa(t->box, dim ? 110 : LV_OPA_COVER, 0);
    lv_obj_set_flag(t->logo, LV_OBJ_FLAG_HIDDEN, logo->key == NULL);
    lv_obj_set_flag(t->letter, LV_OBJ_FLAG_HIDDEN, logo->key != NULL);
    if (logo->key != NULL) {
        lv_image_set_src(t->logo, logo->image);
        lv_obj_set_style_image_recolor(t->logo, lv_color_hex(glow), 0);
    } else {
        char letter[2] = {name[0], 0};
        lv_label_set_text(t->letter, letter);
        lv_obj_set_style_text_color(t->letter, lv_color_hex(glow), 0);
    }
}

static void show_ring(void)
{
    int n = shown.count;
    for (int i = 0; i < DESK_SERVICES; i++) {
        lv_obj_set_flag(ring[i].box, LV_OBJ_FLAG_HIDDEN, i >= n);
        lv_obj_set_flag(names[i], LV_OBJ_FLAG_HIDDEN, i >= n);
        if (i >= n) {
            continue;
        }
        float angle = (float)i / n * 2 * (float)M_PI - (float)M_PI / 2;
        int x = CX + (int)lroundf(RADIUS * cosf(angle)), y = CY + (int)lroundf(RADIUS * sinf(angle));
        lv_obj_set_pos(ring[i].box, x - BIG / 2, y - BIG / 2);
        tile_set(&ring[i], shown.services[i].key, shown.services[i].name, shown.services[i].state == 'u');
        lv_label_set_text(names[i], shown.services[i].name);
        lv_obj_set_pos(names[i], x - 100, y + BIG / 2 + 8);
    }
}

static void show_incident(void)
{
    const typeof(shown.incident) *inc = &shown.incident;
    uint32_t colour = tone_colour(inc->state);
    uint32_t tint = inc->state == 'o' ? 0x1c0d0d : inc->state == 'm' ? 0x12101f : 0x17120a;
    lv_obj_set_style_bg_color(card, lv_color_hex(tint), 0);
    lv_obj_set_style_border_color(card, lv_color_hex(colour), 0);
    tile_set(&card_tile, inc->key, inc->name, false);
    lv_label_set_text(card_name, inc->name);
    lv_label_set_text(card_line, inc->line);
    lv_obj_set_style_text_color(card_line, lv_color_hex(colour), 0);
    lv_label_set_text(card_title, inc->title);
    for (int i = 0; i < DESK_SERVICE_STEPS; i++) {
        bool on = i < inc->step_count;
        lv_obj_set_flag(step_rows[i], LV_OBJ_FLAG_HIDDEN, !on); /* the card shrinks to fit */
        if (on) {
            lv_label_set_text(steps[i], inc->steps[i].status);
            lv_label_set_text(step_times[i], inc->steps[i].time);
            lv_obj_set_style_bg_color(step_dots[i], lv_color_hex(i == 0 ? colour : 0x4a4856), 0);
            lv_obj_set_style_text_color(steps[i], lv_color_hex(i == 0 ? 0xf1eff7 : GREY), 0);
        }
    }
    /* The others, evenly spread below the card. */
    int n = 0;
    for (int i = 0; i < shown.count; i++) {
        n += strcmp(shown.services[i].key, inc->key) != 0;
    }
    int step = n > 1 ? (648 - SMALL) / (n - 1) : 0, k = 0;
    for (int i = 0; i < DESK_SERVICES; i++) {
        lv_obj_add_flag(small[i].box, LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < shown.count && k < DESK_SERVICES; i++) {
        if (strcmp(shown.services[i].key, inc->key) == 0) {
            continue;
        }
        tile_t *t = &small[k];
        lv_obj_remove_flag(t->box, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_pos(t->box, n > 1 ? LEFT + k * step : CX - SMALL / 2, SMALL_Y);
        bool trouble = shown.services[i].state != 'k';
        tile_set(t, shown.services[i].key, shown.services[i].name, false);
        lv_obj_set_style_border_color(t->box, lv_color_hex(trouble ? tone_colour(shown.services[i].state) : 0x24242c), 0);
        k++;
    }
    lv_label_set_text(others, shown.others);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_services_version() == version) {
        return;
    }
    desk_services_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    uint32_t colour = tone_colour(shown.tone);
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(colour), 0);
    lv_obj_set_style_border_opa(pill, shown.tone == 'k' ? 150 : LV_OPA_COVER, 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(colour), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(shown.has_incident ? colour : 0x7c6cf2), 0);
    lv_obj_set_flag(ring_view, LV_OBJ_FLAG_HIDDEN, shown.has_incident);
    lv_obj_set_flag(incident_view, LV_OBJ_FLAG_HIDDEN, !shown.has_incident);
    if (shown.has_incident) {
        show_incident();
    } else {
        show_ring();
    }
}

static void create_ring(lv_obj_t *screen)
{
    ring_view = ui_plain(screen);
    lv_obj_set_size(ring_view, 720, 720);

    /* The glowing check in the middle. */
    lv_obj_t *glow = lv_image_create(ring_view);
    lv_image_set_src(glow, &glow_round);
    lv_image_set_scale(glow, 256 * 300 / 160);
    lv_obj_set_pos(glow, CX - 80, CY - 80);
    lv_obj_set_style_image_recolor(glow, lv_color_hex(GREEN), 0);
    lv_obj_set_style_image_recolor_opa(glow, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(glow, 60, 0);
    lv_obj_t *disc = ui_plain(ring_view);
    lv_obj_set_size(disc, 96, 96);
    lv_obj_set_pos(disc, CX - 48, CY - 48);
    lv_obj_set_style_radius(disc, 48, 0);
    lv_obj_set_style_bg_color(disc, lv_color_hex(GREEN), 0);
    lv_obj_set_style_bg_opa(disc, 36, 0);
    lv_obj_set_style_border_color(disc, lv_color_hex(GREEN), 0);
    lv_obj_set_style_border_opa(disc, 128, 0);
    lv_obj_set_style_border_width(disc, 2, 0);
    static lv_point_precise_t check_points[] = {{0, 17}, {14, 31}, {42, 0}};
    lv_obj_t *check = lv_line_create(disc);
    lv_line_set_points(check, check_points, 3);
    lv_obj_set_style_line_width(check, 7, 0);
    lv_obj_set_style_line_rounded(check, true, 0);
    lv_obj_set_style_line_color(check, lv_color_hex(GREEN), 0);
    lv_obj_center(check);

    for (int i = 0; i < DESK_SERVICES; i++) {
        ring[i] = tile_create(ring_view, BIG);
        names[i] = ui_text(ring_view, &instrument_24, GREY);
        lv_obj_set_width(names[i], 200);
        lv_obj_set_style_text_align(names[i], LV_TEXT_ALIGN_CENTER, 0);
    }
}

static void create_incident(lv_obj_t *screen)
{
    incident_view = ui_plain(screen);
    lv_obj_set_size(incident_view, 720, 720);
    lv_obj_add_flag(incident_view, LV_OBJ_FLAG_HIDDEN);

    card = ui_plain(incident_view);
    lv_obj_set_pos(card, LEFT, 96);
    lv_obj_set_size(card, 648, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_all(card, 28, 0);
    lv_obj_set_style_radius(card, 24, 0);
    lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(card, 2, 0);
    lv_obj_set_style_border_opa(card, 115, 0);
    lv_obj_set_layout(card, LV_LAYOUT_FLEX);
    lv_obj_set_flex_flow(card, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(card, 14, 0);

    lv_obj_t *top = ui_plain(card);
    lv_obj_set_size(top, LV_PCT(100), CARD_TILE);
    card_tile = tile_create(top, CARD_TILE);
    card_name = ui_text(top, &instrument_28_bold, 0xf1eff7);
    lv_obj_set_pos(card_name, CARD_TILE + 20, 2);
    card_line = ui_text(top, &instrument_24, AMBER);
    lv_obj_set_pos(card_line, CARD_TILE + 20, 40);

    card_title = ui_text(card, &instrument_24, 0xf1eff7);
    lv_obj_set_width(card_title, LV_PCT(100));
    lv_label_set_long_mode(card_title, LV_LABEL_LONG_DOT);
    lv_obj_set_style_max_height(card_title, 3 * 32, 0);
    lv_obj_set_style_text_line_space(card_title, 4, 0);

    for (int i = 0; i < DESK_SERVICE_STEPS; i++) {
        lv_obj_t *row = step_rows[i] = ui_plain(card);
        lv_obj_set_size(row, LV_PCT(100), 32);
        step_dots[i] = ui_plain(row);
        lv_obj_set_size(step_dots[i], 12, 12);
        lv_obj_set_style_radius(step_dots[i], 6, 0);
        lv_obj_set_style_bg_opa(step_dots[i], LV_OPA_COVER, 0);
        lv_obj_align(step_dots[i], LV_ALIGN_LEFT_MID, 0, 0);
        steps[i] = ui_text(row, &instrument_24, GREY);
        lv_obj_align(steps[i], LV_ALIGN_LEFT_MID, 26, 0);
        step_times[i] = ui_text(row, &instrument_24, GREY);
        lv_obj_align(step_times[i], LV_ALIGN_RIGHT_MID, 0, 0);
    }

    for (int i = 0; i < DESK_SERVICES; i++) {
        small[i] = tile_create(incident_view, SMALL);
        lv_obj_add_flag(small[i].box, LV_OBJ_FLAG_HIDDEN);
    }
    others = ui_text(incident_view, &instrument_24, 0x6c6a78);
    lv_obj_set_width(others, 648);
    lv_obj_set_style_text_align(others, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(others, LEFT, SMALL_Y + SMALL + 24);
}

void screen_services_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* House's quiet violet from the top; the incident's colour during one. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, GREY);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    pill = ui_plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 4, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_border_width(pill, 2, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 24);
    pill_text = ui_text(pill, &instrument_24, GREEN);
    lv_obj_set_style_text_letter_space(pill_text, 2, 0);

    create_ring(screen);
    create_incident(screen);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
