/* The Home panel's laundry (plan.md M20), as in the desk panels mockup and the
 * hub's laundry card: the washer and dryer as two portholes, a ring for how far
 * the program is and water in the glass door, the minutes left in the middle (a
 * check once done), then the program and when it is ready, or "Take it out".
 * Shown only while a machine runs, is paused, has an error or is done; the
 * wording and colours come from the hub (app/desk_home.py).
 *
 * Lifted (plan.md M27): mostly only one machine is on, so then it alone is large, its
 * words beside it, the other as one glass line at the bottom; both side by side only when
 * both are on. The hub paints a chrome rim round each door (app/paint_laundry.py), a
 * highlight lies on the glass, and while it runs a few bubbles rise through the water. */

#include "screen_laundry.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "esp_random.h"
#include "lvgl.h"
#include "arrive.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_52_bold);
LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define RING 250
#define DOOR 190
#define TOP 110
/* One machine on its own (plan.md M27, the owner's wish: mostly only one runs). */
#define SOLO_RING 330
#define SOLO_DOOR 260
#define SOLO_TOP 120
#define SOLO_TEXT 384   /* the column beside the porthole */
#define BAR_TOP 600     /* the other machine, as one line */
#define BUBBLES 6
#define BUBBLE_MS 80

static lv_obj_t *self, *pill, *pill_label, *bar, *bar_name, *bar_state, *bubbles[BUBBLES];
static int solo = -2; /* the machine shown on its own, -1 for both side by side; as laid out */
static int bubble_y[BUBBLES];
static struct {
    lv_obj_t *box, *ring, *door, *water, *minutes, *unit, *check, *mark, *name, *line, *status;
} ports[2];
EXT_RAM_BSS_ATTR static desk_laundry_t shown; /* off the LVGL task's small stack */

static lv_obj_t *centred(lv_obj_t *parent, const lv_font_t *font, uint32_t colour)
{
    lv_obj_t *label = ui_text(parent, font, colour);
    lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    return label;
}

static void paint(int i)
{
    typeof(shown.machines[0]) *m = &shown.machines[i];
    bool running = strcmp(m->state, "running") == 0, paused = strcmp(m->state, "paused") == 0;
    bool done = strcmp(m->state, "done") == 0, error = strcmp(m->state, "error") == 0;
    bool idle = !running && !paused && !done && !error;

    lv_arc_set_value(ports[i].ring, m->progress);
    lv_obj_set_style_arc_color(ports[i].ring, lv_color_hex(m->colour), LV_PART_INDICATOR);
    lv_obj_set_style_arc_opa(ports[i].ring, m->progress > 0 ? LV_OPA_COVER : LV_OPA_TRANSP, LV_PART_INDICATOR);
    lv_obj_set_style_border_color(ports[i].door, lv_color_hex(done || paused || error ? m->colour : 0xffffff), 0);
    lv_obj_set_style_border_opa(ports[i].door, done || paused || error ? 110 : 22, 0);

    /* Water rises with the program: from just under the middle to near the bottom. */
    int door = solo == i ? SOLO_DOOR : DOOR;
    lv_obj_set_flag(ports[i].water, LV_OBJ_FLAG_HIDDEN, !(running || paused));
    lv_obj_set_style_bg_color(ports[i].water, lv_color_hex(m->water), 0);
    lv_obj_set_y(ports[i].water, door * (45 + 30 * m->progress / 1000) / 100);

    bool counting = (running || paused) && m->minutes >= 0;
    lv_obj_set_flag(ports[i].minutes, LV_OBJ_FLAG_HIDDEN, !counting);
    lv_obj_set_flag(ports[i].unit, LV_OBJ_FLAG_HIDDEN, !counting);
    if (counting) {
        lv_label_set_text_fmt(ports[i].minutes, "%d", m->minutes);
    }
    lv_obj_set_flag(ports[i].check, LV_OBJ_FLAG_HIDDEN, !done);
    lv_obj_set_flag(ports[i].mark, LV_OBJ_FLAG_HIDDEN, !error);

    lv_label_set_text(ports[i].name, m->name);
    lv_label_set_text(ports[i].line, m->line);
    lv_label_set_text(ports[i].status, m->status);
    lv_obj_set_style_text_color(ports[i].status, lv_color_hex(m->status_colour), 0);
    lv_obj_set_style_opa(ports[i].box, idle ? 115 : LV_OPA_COVER, 0);
}

static bool active(int i)
{
    return i < shown.count && strcmp(shown.machines[i].state, "idle") != 0;
}

/* Side by side, or one machine large with its words beside it and the other as a line. */
static void arrange(int which)
{
    if (which == solo) {
        return;
    }
    solo = which;
    for (int i = 0; i < 2; i++) {
        bool alone = which == i, single = which >= 0;
        int ring = alone ? SOLO_RING : RING, door = alone ? SOLO_DOOR : DOOR;
        lv_obj_set_flag(ports[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.count || (single && !alone));
        lv_obj_set_size(ports[i].box, alone ? 648 : 324, alone ? 460 : 560);
        lv_obj_set_pos(ports[i].box, alone ? LEFT : 36 + i * 324, alone ? SOLO_TOP : TOP);
        lv_obj_set_size(ports[i].ring, ring, ring);
        lv_obj_align(ports[i].ring, alone ? LV_ALIGN_TOP_LEFT : LV_ALIGN_TOP_MID, 0, 0);
        lv_obj_set_size(ports[i].door, door, door);
        lv_obj_align(ports[i].door, alone ? LV_ALIGN_TOP_LEFT : LV_ALIGN_TOP_MID, alone ? (ring - door) / 2 : 0,
                     (ring - door) / 2);
        lv_obj_set_size(ports[i].water, door, door);
        lv_obj_set_style_text_align(ports[i].name, alone ? LV_TEXT_ALIGN_LEFT : LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_style_text_align(ports[i].line, alone ? LV_TEXT_ALIGN_LEFT : LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_style_text_align(ports[i].status, alone ? LV_TEXT_ALIGN_LEFT : LV_TEXT_ALIGN_CENTER, 0);
        if (alone) {
            lv_obj_align(ports[i].name, LV_ALIGN_TOP_LEFT, SOLO_TEXT - LEFT, 92);
            lv_obj_align(ports[i].line, LV_ALIGN_TOP_LEFT, SOLO_TEXT - LEFT, 156);
            lv_obj_align(ports[i].status, LV_ALIGN_TOP_LEFT, SOLO_TEXT - LEFT, 196);
        } else {
            lv_obj_align(ports[i].name, LV_ALIGN_TOP_MID, 0, RING + 24);
            lv_obj_align(ports[i].line, LV_ALIGN_TOP_MID, 0, RING + 80);
            lv_obj_align(ports[i].status, LV_ALIGN_TOP_MID, 0, RING + 116);
        }
    }
    lv_obj_set_flag(bar, LV_OBJ_FLAG_HIDDEN, which < 0 || shown.count < 2);
}

/* While the machine on its own runs: a few bubbles rise through its water. */
static void rise(lv_timer_t *timer)
{
    bool on = solo >= 0 && lv_screen_active() == self && strcmp(shown.machines[solo].state, "running") == 0;
    for (int i = 0; i < BUBBLES; i++) {
        if (!on) {
            lv_obj_add_flag(bubbles[i], LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        if (lv_obj_get_parent(bubbles[i]) != ports[solo].door) {
            lv_obj_set_parent(bubbles[i], ports[solo].door);
        }
        lv_obj_remove_flag(bubbles[i], LV_OBJ_FLAG_HIDDEN);
        bubble_y[i] -= 2 + i % 3;
        int top = lv_obj_get_y(ports[solo].water);
        if (bubble_y[i] < top) {
            bubble_y[i] = SOLO_DOOR - 10 - (int)(esp_random() % 40);
            lv_obj_set_x(bubbles[i], 40 + (int)(esp_random() % (SOLO_DOOR - 80)));
        }
        lv_obj_set_y(bubbles[i], bubble_y[i]);
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_laundry_version() == version) {
        return;
    }
    shown = desk_laundry();
    version = shown.version;
    if (!shown.present) {
        return;
    }
    char caps[32];
    ui_upper(caps, sizeof caps, shown.headline);
    lv_label_set_text(pill_label, caps);
    lv_obj_set_style_text_color(pill_label, lv_color_hex(shown.headline_colour), 0);
    lv_obj_set_style_bg_color(pill, lv_color_hex(shown.headline_colour), 0);
    /* Mostly only one machine is on: then it alone is large. */
    int which = active(0) && !active(1) ? 0 : (active(1) && !active(0) ? 1 : -1);
    solo = -2; /* lay out again: the machines may have changed */
    arrange(which);
    for (int i = 0; i < 2; i++) {
        if (i < shown.count) {
            paint(i);
        }
    }
    if (which >= 0 && shown.count > 1) {
        int other = 1 - which;
        lv_label_set_text(bar_name, shown.machines[other].name);
        lv_label_set_text(bar_state, active(other) ? shown.machines[other].status : "off");
    }
}

void screen_laundry_create(lv_obj_t *screen)
{
    self = screen;
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    lv_obj_t *header = centred(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "LAUNDRY");
    lv_obj_set_pos(header, LEFT, 30);
    pill = ui_plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 6, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_opa(pill, 50, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 22);
    pill_label = centred(pill, &instrument_24, 0xffffff);
    lv_obj_set_style_text_letter_space(pill_label, 1, 0);

    for (int i = 0; i < 2; i++) {
        lv_obj_t *box = ports[i].box = ui_plain(screen);
        lv_obj_set_size(box, 324, 560);
        lv_obj_set_pos(box, 36 + i * 324, TOP);

        lv_obj_t *ring = ports[i].ring = lv_arc_create(box);
        arrive_sweep(ring);
        lv_obj_remove_style(ring, NULL, LV_PART_KNOB);
        lv_obj_remove_flag(ring, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_set_size(ring, RING, RING);
        lv_obj_align(ring, LV_ALIGN_TOP_MID, 0, 0);
        lv_arc_set_rotation(ring, 270);
        lv_arc_set_bg_angles(ring, 0, 360);
        lv_arc_set_range(ring, 0, 1000);
        lv_obj_set_style_arc_width(ring, 8, LV_PART_MAIN);
        lv_obj_set_style_arc_width(ring, 8, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(ring, lv_color_hex(0x1f1e25), LV_PART_MAIN);
        lv_obj_set_style_arc_rounded(ring, true, LV_PART_INDICATOR);

        /* The glass door, with the water inside it. */
        lv_obj_t *door = ports[i].door = ui_plain(box);
        lv_obj_set_size(door, DOOR, DOOR);
        lv_obj_align(door, LV_ALIGN_TOP_MID, 0, (RING - DOOR) / 2);
        lv_obj_set_style_radius(door, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_clip_corner(door, true, 0);
        lv_obj_set_style_bg_opa(door, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(door, lv_color_hex(0x13131a), 0);
        lv_obj_set_style_bg_grad_color(door, lv_color_hex(0x0b0b10), 0);
        lv_obj_set_style_bg_grad_dir(door, LV_GRAD_DIR_VER, 0);
        lv_obj_set_style_border_width(door, 6, 0);
        lv_obj_set_style_border_post(door, true, 0);
        ports[i].water = ui_plain(door);
        lv_obj_set_size(ports[i].water, DOOR, DOOR);
        lv_obj_set_style_bg_opa(ports[i].water, 120, 0);
        lv_obj_t *shine = ui_plain(door); /* light on the glass, top left */
        lv_obj_set_size(shine, 90, 46);
        lv_obj_set_pos(shine, 26, 30);
        lv_obj_set_style_radius(shine, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(shine, lv_color_white(), 0);
        lv_obj_set_style_bg_opa(shine, 12, 0);

        ports[i].minutes = centred(door, &instrument_52_bold, 0xffffff);
        lv_obj_align(ports[i].minutes, LV_ALIGN_CENTER, 0, -12);
        ports[i].unit = centred(door, &instrument_24, 0xd6d3df);
        lv_label_set_text(ports[i].unit, "min");
        lv_obj_align(ports[i].unit, LV_ALIGN_CENTER, 0, 30);

        /* Done: a check; an error: an exclamation mark. */
        static lv_point_precise_t tick_points[] = {{0, 26}, {22, 48}, {66, 0}};
        ports[i].check = lv_line_create(door);
        lv_line_set_points(ports[i].check, tick_points, 3);
        lv_obj_set_style_line_width(ports[i].check, 9, 0);
        lv_obj_set_style_line_rounded(ports[i].check, true, 0);
        lv_obj_set_style_line_color(ports[i].check, lv_color_hex(0x3fb97f), 0);
        lv_obj_center(ports[i].check);
        ports[i].mark = centred(door, &instrument_52_bold, 0xe5646a);
        lv_label_set_text(ports[i].mark, "!");
        lv_obj_center(ports[i].mark);

        ports[i].name = centred(box, &instrument_40, 0xffffff);
        lv_obj_align(ports[i].name, LV_ALIGN_TOP_MID, 0, RING + 24);
        ports[i].line = ui_one_line(box, &instrument_24, 0xb4b1c2, 300);
        lv_obj_set_style_text_align(ports[i].line, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_align(ports[i].line, LV_ALIGN_TOP_MID, 0, RING + 80);
        ports[i].status = ui_one_line(box, &instrument_24, 0xffffff, 300);
        lv_obj_set_style_text_align(ports[i].status, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_align(ports[i].status, LV_ALIGN_TOP_MID, 0, RING + 116);
        lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);
    }

    /* The other machine, as one glass line along the bottom. */
    bar = ui_plain(screen);
    lv_obj_set_size(bar, 648, 76);
    lv_obj_set_pos(bar, LEFT, BAR_TOP);
    lv_obj_set_style_radius(bar, 38, 0);
    lv_obj_set_style_bg_opa(bar, 150, 0);
    lv_obj_set_style_bg_color(bar, lv_color_hex(0x16151c), 0);
    lv_obj_set_style_border_width(bar, 1, 0);
    lv_obj_set_style_border_color(bar, lv_color_white(), 0);
    lv_obj_set_style_border_opa(bar, 30, 0);
    bar_name = ui_text(bar, &instrument_24, 0xe6e3ef);
    lv_obj_align(bar_name, LV_ALIGN_LEFT_MID, 34, 0);
    bar_state = ui_text(bar, &instrument_24, 0x8a8794);
    lv_obj_align(bar_state, LV_ALIGN_RIGHT_MID, -34, 0);
    lv_obj_add_flag(bar, LV_OBJ_FLAG_HIDDEN);

    for (int i = 0; i < BUBBLES; i++) {
        bubbles[i] = ui_plain(screen);
        int size = 6 + (i % 3) * 3;
        lv_obj_set_size(bubbles[i], size, size);
        lv_obj_set_style_radius(bubbles[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(bubbles[i], 2, 0);
        lv_obj_set_style_border_color(bubbles[i], lv_color_hex(0xdcd7ff), 0);
        lv_obj_set_style_border_opa(bubbles[i], 140, 0);
        lv_obj_add_flag(bubbles[i], LV_OBJ_FLAG_HIDDEN);
        bubble_y[i] = -1000; /* placed on the first step */
    }
    lv_timer_create(rise, BUBBLE_MS, NULL);

    lv_timer_create(tick, 1000, NULL);
}
