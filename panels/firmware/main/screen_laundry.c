/* The Home panel's laundry (plan.md M20), as in the desk panels mockup and the
 * hub's laundry card: the washer and dryer as two portholes, a ring for how far
 * the program is and water in the glass door, the minutes left in the middle (a
 * check once done), then the program and when it is ready, or "Take it out".
 * Shown only while a machine runs, is paused, has an error or is done; the
 * wording and colours come from the hub (app/desk_home.py). */

#include "screen_laundry.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
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

static lv_obj_t *pill, *pill_label;
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
    lv_obj_set_flag(ports[i].water, LV_OBJ_FLAG_HIDDEN, !(running || paused));
    lv_obj_set_style_bg_color(ports[i].water, lv_color_hex(m->water), 0);
    lv_obj_set_y(ports[i].water, DOOR * (45 + 30 * m->progress / 1000) / 100);

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
    for (int i = 0; i < 2; i++) {
        lv_obj_set_flag(ports[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i < shown.count) {
            paint(i);
        }
    }
}

void screen_laundry_create(lv_obj_t *screen)
{
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

    lv_timer_create(tick, 1000, NULL);
}
