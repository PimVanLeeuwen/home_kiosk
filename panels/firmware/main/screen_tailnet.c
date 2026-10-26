/* The House panel's Tailnet screen (plan.md Open items, designed 2026-10-12): the NAS
 * in the middle and every device round it, a line per device by how it connects
 * (green and direct, violet and dashed through a relay, still grey when idle, dotted
 * when offline), the names on the outside; below, the NAS and the online devices with
 * their Tailscale address. Amber while tailscaled has a health warning. Words and
 * places from the hub (app/desk_tailnet.py).
 *
 * The lines are drawn once into a canvas, when the hub's answer changes; only one
 * small light per live line moves, from the NAS outwards (chosen 2026-10-22). */

#include "screen_tailnet.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define MAP_TOP 84
#define MAP_W 648
#define MAP_H 380
#define SELF 96
#define PEER 68
#define NAME_W 320
#define LIST_TOP 486
#define ROW_H 40
#define LIGHT 12
#define PARTICLES 3 /* per live link: the traffic as a flow (plan.md M27) */

#define GREEN 0x5fd39c
#define VIOLET 0xb4a9ff
#define NAS 0x7c6cf2
#define AMBER 0xf0bd5a
#define IDLE 0x6c6a78
#define DIM 0x4a4955

typedef struct {
    lv_obj_t *light;
    int32_t x0, y0, x1, y1; /* where the light runs, in screen pixels */
} path_t;

static lv_obj_t *sky, *title, *pill, *pill_text, *canvas, *self_tile, *self_label;
static struct {
    lv_obj_t *tile, *label, *name;
} nodes[DESK_TAILNET_NODES];
static struct {
    lv_obj_t *box, *dot, *name, *ip, *via;
} rows[DESK_TAILNET_ROWS];
static path_t paths[DESK_TAILNET_NODES][PARTICLES];
EXT_RAM_BSS_ATTR static desk_tailnet_t shown; /* off the LVGL task's small stack */

static uint32_t kind_colour(char kind)
{
    switch (kind) {
    case 'd':
        return GREEN;
    case 'r':
        return VIOLET;
    case 'i':
        return IDLE;
    default:
        return DIM;
    }
}

/* The light slides out and fades in and out at its ends. */
static void move_light(void *var, int32_t at)
{
    path_t *path = var;
    int32_t half = lv_obj_get_width(path->light) / 2;
    lv_obj_set_pos(path->light, path->x0 + (path->x1 - path->x0) * at / 1000 - half,
                   path->y0 + (path->y1 - path->y0) * at / 1000 - half);
    int32_t edge = at < 200 ? at : at > 800 ? 1000 - at : 200;
    lv_opa_t opa = (lv_opa_t)(edge * 255 / 200);
    lv_obj_set_style_bg_opa(path->light, opa, 0);
    lv_obj_set_style_shadow_opa(path->light, opa, 0);
}

/* LVGL's software renderer dashes only straight across or down: a slanted dashed
 * line comes out solid, so dashes are drawn as short segments here. */
static void draw_line(lv_layer_t *layer, char kind, int32_t x0, int32_t y0, int32_t x1, int32_t y1)
{
    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    line.color = lv_color_hex(kind == 'o' ? 0xffffff : kind_colour(kind));
    line.width = kind == 'd' || kind == 'r' ? 3 : 2;
    line.opa = kind == 'o' ? 60 : kind == 'i' ? 150 : 120;
    line.round_start = line.round_end = 1;
    int dash = kind == 'r' ? 10 : kind == 'o' ? 3 : 0, gap = kind == 'r' ? 8 : 10;
    float dx = x1 - x0, dy = y1 - y0, length = sqrtf(dx * dx + dy * dy);
    if (dash == 0 || length < 1) {
        line.p1.x = x0, line.p1.y = y0;
        line.p2.x = x1, line.p2.y = y1;
        lv_draw_line(layer, &line);
        return;
    }
    for (float at = 0; at < length; at += dash + gap) {
        float to = at + dash < length ? at + dash : length;
        line.p1.x = x0 + (int32_t)(dx * at / length), line.p1.y = y0 + (int32_t)(dy * at / length);
        line.p2.x = x0 + (int32_t)(dx * to / length), line.p2.y = y0 + (int32_t)(dy * to / length);
        lv_draw_line(layer, &line);
    }
}

static void show_map(void)
{
    uint32_t nas = shown.warn ? AMBER : NAS;
    lv_obj_set_style_border_color(self_tile, lv_color_hex(nas), 0);
    lv_obj_set_style_text_color(self_label, lv_color_hex(shown.warn ? AMBER : 0xffffff), 0);

    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    memset(buf->data, 0, buf->header.stride * MAP_H);
    lv_layer_t layer;
    lv_canvas_init_layer(canvas, &layer);
    const int32_t cx = MAP_W / 2, cy = MAP_H * 48 / 100;
    for (int i = 0; i < DESK_TAILNET_NODES; i++) {
        for (int k = 0; k < PARTICLES; k++) {
            lv_anim_delete(&paths[i][k], move_light);
            lv_obj_add_flag(paths[i][k].light, LV_OBJ_FLAG_HIDDEN);
        }
        bool here = i < shown.node_count;
        lv_obj_set_flag(nodes[i].tile, LV_OBJ_FLAG_HIDDEN, !here);
        lv_obj_set_flag(nodes[i].name, LV_OBJ_FLAG_HIDDEN, !here);
        if (!here) {
            continue;
        }
        const typeof(shown.nodes[0]) *node = &shown.nodes[i];
        int32_t px = node->x * MAP_W / 100, py = node->y * MAP_H / 100;

        /* The line stops short of both tiles. */
        float dx = px - cx, dy = py - cy, length = sqrtf(dx * dx + dy * dy);
        if (length < 1) {
            length = 1;
        }
        float ux = dx / length, uy = dy / length;
        int32_t x0 = cx + (int32_t)(ux * (SELF / 2 + 10)), y0 = cy + (int32_t)(uy * (SELF / 2 + 10));
        int32_t x1 = px - (int32_t)(ux * (PEER / 2 + 10)), y1 = py - (int32_t)(uy * (PEER / 2 + 10));
        draw_line(&layer, node->kind, x0, y0, x1, y1);

        bool off = node->kind == 'o';
        uint32_t colour = kind_colour(node->kind);
        lv_obj_set_pos(nodes[i].tile, LEFT + px - PEER / 2, MAP_TOP + py - PEER / 2);
        lv_obj_set_style_border_color(nodes[i].tile, lv_color_hex(off ? 0x26252c : colour), 0);
        lv_label_set_text(nodes[i].label, node->label);
        lv_obj_set_style_text_color(nodes[i].label, lv_color_hex(off ? IDLE : 0xffffff), 0);

        /* The name on the outside: above a tile in the top half, below it in the bottom. */
        char name[64];
        if (off && node->seen[0]) {
            snprintf(name, sizeof name, "%s · %s", node->name, node->seen);
        } else {
            snprintf(name, sizeof name, "%s%s", node->name, node->exit ? " · exit" : "");
        }
        lv_label_set_text(nodes[i].name, name);
        lv_obj_set_style_text_color(nodes[i].name, lv_color_hex(off ? IDLE : 0xc9c6d6), 0);
        /* As wide as the name (up to NAME_W), under its tile, kept on the screen. */
        int32_t width = lv_text_get_width(name, strlen(name), &instrument_24, 0) + 4;
        width = width < NAME_W ? width : NAME_W;
        lv_obj_set_width(nodes[i].name, width);
        int32_t nx = px - width / 2;
        nx = nx < -LEFT + 8 ? -LEFT + 8 : nx > MAP_W + LEFT - 8 - width ? MAP_W + LEFT - 8 - width : nx;
        int32_t line_h = lv_font_get_line_height(&instrument_24);
        int32_t ny = node->y < 48 ? py - PEER / 2 - 6 - line_h : py + PEER / 2 + 6;
        lv_obj_set_pos(nodes[i].name, LEFT + nx, MAP_TOP + ny);

        /* Its traffic: particles evenly apart, flowing out along the line. */
        for (int k = 0; k < PARTICLES && (node->kind == 'd' || node->kind == 'r'); k++) {
            path_t *path = &paths[i][k];
            *path = (path_t){.light = path->light, .x0 = LEFT + x0, .y0 = MAP_TOP + y0,
                             .x1 = LEFT + x1, .y1 = MAP_TOP + y1};
            lv_obj_set_style_bg_color(path->light, lv_color_hex(colour), 0);
            lv_obj_set_style_shadow_color(path->light, lv_color_hex(colour), 0);
            lv_obj_remove_flag(path->light, LV_OBJ_FLAG_HIDDEN);
            uint32_t ms = 2400 + (uint32_t)length * 3;
            lv_anim_t anim;
            lv_anim_init(&anim);
            lv_anim_set_var(&anim, path);
            lv_anim_set_exec_cb(&anim, move_light);
            lv_anim_set_values(&anim, 0, 1000);
            lv_anim_set_duration(&anim, ms);
            lv_anim_set_delay(&anim, i * 200 + k * ms / PARTICLES);
            lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
            lv_anim_start(&anim);
        }
    }
    lv_canvas_finish_layer(canvas, &layer);
    lv_obj_invalidate(canvas);
}

static void show_rows(void)
{
    for (int i = 0; i < DESK_TAILNET_ROWS; i++) {
        lv_obj_set_flag(rows[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.row_count);
        if (i >= shown.row_count) {
            continue;
        }
        const typeof(shown.rows[0]) *row = &shown.rows[i];
        bool self = row->kind == 's';
        uint32_t colour = self ? (shown.warn ? AMBER : NAS) : kind_colour(row->kind);
        lv_obj_set_style_bg_color(rows[i].dot, lv_color_hex(colour), 0);
        lv_obj_set_style_shadow_color(rows[i].dot, lv_color_hex(colour), 0);
        lv_obj_set_style_shadow_opa(rows[i].dot, row->kind == 'i' ? 0 : 160, 0);
        lv_label_set_text(rows[i].name, row->name);
        lv_label_set_text(rows[i].ip, row->ip);
        lv_label_set_text(rows[i].via, row->via);
        lv_obj_set_style_text_color(rows[i].via, lv_color_hex(self && shown.warn ? AMBER : 0x8a8794), 0);
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_tailnet_version() == version) {
        return;
    }
    desk_tailnet_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(shown.warn ? AMBER : GREEN), 0);
    lv_obj_set_style_border_opa(pill, shown.warn ? LV_OPA_COVER : 150, 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(shown.warn ? AMBER : GREEN), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(shown.warn ? AMBER : NAS), 0);
    show_map();
    show_rows();
}

static lv_obj_t *tile(lv_obj_t *parent, int size, uint32_t fill)
{
    lv_obj_t *box = ui_plain(parent);
    lv_obj_set_size(box, size, size);
    lv_obj_set_style_radius(box, size / 4, 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    backdrops_glass(box);
    lv_obj_set_style_bg_color(box, lv_color_hex(fill), 0);
    lv_obj_set_style_border_width(box, 2, 0);
    return box;
}

void screen_tailnet_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* House's quiet violet from the top; amber while tailscaled warns. */
    sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(NAS), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 60, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
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

    /* The lines, under everything else on the map. */
    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(MAP_W, MAP_H, LV_COLOR_FORMAT_ARGB8888, 0));
    lv_obj_set_pos(canvas, LEFT, MAP_TOP);
    memset(lv_canvas_get_draw_buf(canvas)->data, 0, lv_canvas_get_draw_buf(canvas)->header.stride * MAP_H);

    for (int i = 0; i < DESK_TAILNET_NODES; i++) {
        for (int k = 0; k < PARTICLES; k++) {
            lv_obj_t *light = paths[i][k].light = ui_plain(screen);
            lv_obj_set_size(light, LIGHT - 3 * k, LIGHT - 3 * k); /* the first a little larger */
            lv_obj_set_style_radius(light, LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_shadow_width(light, 14, 0);
            lv_obj_add_flag(light, LV_OBJ_FLAG_HIDDEN);
        }

        nodes[i].tile = tile(screen, PEER, 0x101015);
        lv_obj_add_flag(nodes[i].tile, LV_OBJ_FLAG_HIDDEN);
        nodes[i].label = ui_text(nodes[i].tile, &instrument_28_bold, 0xffffff);
        lv_obj_center(nodes[i].label);
        nodes[i].name = ui_one_line(screen, &instrument_24, 0xc9c6d6, NAME_W);
        lv_obj_set_style_text_align(nodes[i].name, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_add_flag(nodes[i].name, LV_OBJ_FLAG_HIDDEN);
    }

    self_tile = tile(screen, SELF, 0x15132a);
    lv_obj_set_style_border_width(self_tile, 3, 0);
    lv_obj_set_pos(self_tile, LEFT + MAP_W / 2 - SELF / 2, MAP_TOP + MAP_H * 48 / 100 - SELF / 2);
    self_label = ui_text(self_tile, &instrument_28_bold, 0xffffff);
    lv_label_set_text(self_label, "NAS");
    lv_obj_center(self_label);

    /* The NAS and the online devices: a dot, the name, the address, how it connects. */
    for (int i = 0; i < DESK_TAILNET_ROWS; i++) {
        lv_obj_t *box = rows[i].box = ui_plain(screen);
        lv_obj_set_size(box, MAP_W, ROW_H);
        lv_obj_set_pos(box, LEFT, LIST_TOP + i * ROW_H);
        lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);
        rows[i].dot = ui_plain(box);
        lv_obj_set_size(rows[i].dot, 12, 12);
        lv_obj_set_style_radius(rows[i].dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(rows[i].dot, LV_OPA_COVER, 0);
        lv_obj_set_style_shadow_width(rows[i].dot, 10, 0);
        lv_obj_align(rows[i].dot, LV_ALIGN_LEFT_MID, 2, 0);
        rows[i].name = ui_one_line(box, &instrument_24, 0xf1eff7, 250);
        lv_obj_align(rows[i].name, LV_ALIGN_LEFT_MID, 28, 0);
        rows[i].ip = ui_one_line(box, &instrument_24, 0x8a8794, 170);
        lv_obj_align(rows[i].ip, LV_ALIGN_LEFT_MID, 290, 0);
        rows[i].via = ui_one_line(box, &instrument_24, 0x8a8794, 180);
        lv_obj_set_style_text_align(rows[i].via, LV_TEXT_ALIGN_RIGHT, 0);
        lv_obj_align(rows[i].via, LV_ALIGN_RIGHT_MID, 0, 0);
    }

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
