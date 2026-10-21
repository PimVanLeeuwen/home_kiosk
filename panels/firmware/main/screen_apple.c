/* The Home panel's Apple devices (plan.md M20), as in the desk panels mockup: the
 * house as a plan of its rooms, the Apple TVs and HomePods as orbs in them (amber
 * when offline), the room where something plays lit in its colour, and what plays
 * in a bar below. Read only; the wording comes from the hub (app/desk_home.py). */

#include "screen_apple.h"

#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define WIDTH 648
#define TOP 90
#define PLAN_H 420
#define GAP 12
#define ORB 76
#define OFFLINE 0xe0a23b

static lv_obj_t *pill, *pill_label, *bar, *bar_stripe, *bar_title, *bar_where;
static struct {
    lv_obj_t *box, *name, *orbs[4], *glyphs[4];
} rooms[3];
EXT_RAM_BSS_ATTR static desk_apple_t shown; /* off the LVGL task's small stack */

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
    lv_label_set_long_mode(label, LV_LABEL_LONG_DOT);
    lv_label_set_text(label, "");
    return label;
}

static void upper(char *to, size_t size, const char *from)
{
    size_t i = 0;
    for (; from[i] && i < size - 1; i++) {
        to[i] = (from[i] >= 'a' && from[i] <= 'z') ? from[i] - 32 : from[i];
    }
    to[i] = '\0';
}

/* The room boxes: the first (the living room) takes the left half of the plan,
 * the others share the right half. */
static void place(int count)
{
    int half = (WIDTH - GAP) / 2;
    for (int i = 0; i < count; i++) {
        if (count == 1) {
            lv_obj_set_size(rooms[i].box, WIDTH, PLAN_H);
            lv_obj_set_pos(rooms[i].box, LEFT, TOP);
        } else if (i == 0) {
            lv_obj_set_size(rooms[i].box, half, PLAN_H);
            lv_obj_set_pos(rooms[i].box, LEFT, TOP);
        } else {
            int height = count == 2 ? PLAN_H : (PLAN_H - GAP) / 2;
            lv_obj_set_size(rooms[i].box, half, height);
            lv_obj_set_pos(rooms[i].box, LEFT + half + GAP, TOP + (i - 1) * (height + GAP));
        }
    }
}

/* A device's glyph: a TV is a wide screen, a HomePod a tall rounded body, a
 * HomePod mini a small ball. */
static void shape(lv_obj_t *glyph, const char *kind, uint32_t colour)
{
    if (strcmp(kind, "tv") == 0) {
        lv_obj_set_size(glyph, 40, 26);
        lv_obj_set_style_radius(glyph, 4, 0);
    } else if (strcmp(kind, "homepod_mini") == 0) {
        lv_obj_set_size(glyph, 26, 26);
        lv_obj_set_style_radius(glyph, LV_RADIUS_CIRCLE, 0);
    } else {
        lv_obj_set_size(glyph, 26, 36);
        lv_obj_set_style_radius(glyph, 11, 0);
    }
    lv_obj_set_style_bg_color(glyph, lv_color_hex(colour), 0);
    lv_obj_center(glyph);
}

static void paint(int i)
{
    typeof(shown.rooms[0]) *room = &shown.rooms[i];
    lv_obj_t *box = rooms[i].box;
    bool lit = room->glow != 0;
    lv_obj_set_style_bg_color(box, lv_color_hex(lit ? room->glow : 0x101015), 0);
    lv_obj_set_style_bg_opa(box, lit ? 46 : LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(box, lv_color_hex(lit ? room->glow : 0xffffff), 0);
    lv_obj_set_style_border_opa(box, lit ? 170 : 26, 0);
    lv_obj_set_style_shadow_opa(box, lit ? 120 : 0, 0);
    lv_obj_set_style_shadow_color(box, lv_color_hex(room->glow), 0);
    lv_label_set_text(rooms[i].name, room->name);
    lv_obj_set_style_text_color(rooms[i].name, lv_color_hex(lit ? 0xffffff : 0xb4b1c2), 0);

    for (int d = 0; d < 4; d++) {
        lv_obj_set_flag(rooms[i].orbs[d], LV_OBJ_FLAG_HIDDEN, d >= room->devices);
        if (d >= room->devices) {
            continue;
        }
        bool online = room->device[d].online;
        lv_obj_t *orb = rooms[i].orbs[d];
        lv_obj_set_style_bg_color(orb, lv_color_hex(online ? 0x1f1e27 : 0x2a1f0e), 0);
        lv_obj_set_style_border_color(orb, lv_color_hex(online ? (lit ? room->glow : 0xffffff) : OFFLINE), 0);
        lv_obj_set_style_border_opa(orb, online ? (lit ? 200 : 40) : 220, 0);
        shape(rooms[i].glyphs[d], room->device[d].kind, online ? 0xe6e3ef : OFFLINE);
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_apple_version() == version) {
        return;
    }
    shown = desk_apple();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    char caps[24];
    upper(caps, sizeof caps, shown.headline);
    lv_label_set_text(pill_label, caps);
    lv_obj_set_style_text_color(pill_label, lv_color_hex(shown.headline_colour), 0);
    lv_obj_set_style_bg_color(pill, lv_color_hex(shown.headline_colour), 0);
    place(shown.count);
    for (int i = 0; i < 3; i++) {
        lv_obj_set_flag(rooms[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i < shown.count) {
            paint(i);
        }
    }
    if (shown.has_playing) {
        lv_label_set_text(bar_title, shown.title);
        lv_label_set_text(bar_where, shown.where);
        lv_obj_set_style_bg_color(bar_stripe, lv_color_hex(shown.playing_colour), 0);
        lv_obj_set_style_text_color(bar_title, lv_color_white(), 0);
    } else {
        lv_label_set_text(bar_title, "Nothing playing");
        lv_label_set_text(bar_where, "");
        lv_obj_set_style_bg_color(bar_stripe, lv_color_hex(0x2a2833), 0);
        lv_obj_set_style_text_color(bar_title, lv_color_hex(0x8a8794), 0);
    }
}

void screen_apple_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *header = text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "APPLE DEVICES");
    lv_obj_set_pos(header, LEFT, 30);
    pill = plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 6, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_opa(pill, 50, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 22);
    pill_label = text(pill, &instrument_24, 0xffffff);
    lv_label_set_long_mode(pill_label, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_letter_space(pill_label, 1, 0);

    for (int i = 0; i < 3; i++) {
        lv_obj_t *box = rooms[i].box = plain(screen);
        lv_obj_set_style_radius(box, 22, 0);
        lv_obj_set_style_border_width(box, 2, 0);
        lv_obj_set_style_shadow_width(box, 40, 0);
        rooms[i].name = text(box, &instrument_28_bold, 0xb4b1c2);
        lv_obj_set_width(rooms[i].name, (WIDTH - GAP) / 2 - 48);
        lv_obj_set_pos(rooms[i].name, 22, 18);

        /* The devices, in a row in the middle of the room, under its name. */
        lv_obj_t *row = plain(box);
        lv_obj_set_size(row, LV_PCT(100), ORB);
        lv_obj_align(row, LV_ALIGN_CENTER, 0, 26);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(row, 14, 0);
        for (int d = 0; d < 4; d++) {
            lv_obj_t *orb = rooms[i].orbs[d] = plain(row);
            lv_obj_set_size(orb, ORB, ORB);
            lv_obj_set_style_radius(orb, LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_bg_opa(orb, LV_OPA_COVER, 0);
            lv_obj_set_style_border_width(orb, 3, 0);
            rooms[i].glyphs[d] = plain(orb);
            lv_obj_set_style_bg_opa(rooms[i].glyphs[d], LV_OPA_COVER, 0);
        }
        lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);
    }

    /* What plays, in a bar under the plan. */
    bar = plain(screen);
    lv_obj_set_size(bar, WIDTH, 132);
    lv_obj_set_pos(bar, LEFT, TOP + PLAN_H + 24);
    lv_obj_set_style_radius(bar, 22, 0);
    lv_obj_set_style_clip_corner(bar, true, 0);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(bar, lv_color_hex(0x101015), 0);
    bar_stripe = plain(bar);
    lv_obj_set_size(bar_stripe, 10, LV_PCT(100));
    lv_obj_set_style_bg_opa(bar_stripe, LV_OPA_COVER, 0);
    bar_title = text(bar, &instrument_28_bold, 0xffffff);
    lv_obj_set_width(bar_title, WIDTH - 72);
    lv_obj_set_pos(bar_title, 36, 28);
    bar_where = text(bar, &instrument_24, 0xb4b1c2);
    lv_obj_set_width(bar_where, WIDTH - 72);
    lv_obj_set_pos(bar_where, 36, 74);

    lv_timer_create(tick, 1000, NULL);
}
