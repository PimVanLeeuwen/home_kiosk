/* The Home panel's Apple devices (plan.md M20), as in the desk panels mockup: the
 * house as a plan of its rooms, the Apple TVs and HomePods as orbs in them (amber
 * when offline), the room where something plays lit in its colour, and what plays
 * in a bar below. Read only; the wording comes from the hub (app/desk_home.py).
 *
 * The Thread mesh (2026-10-23), as on the hub's card: the border routers linked in a
 * chain per room, the rooms linked where their routers are nearest and the last room
 * back to the first; a gentle curve per link, with a pulse of light running along it,
 * or dashed amber when a device at either end is offline or its Thread is down. Orbs
 * that play send out ripples. The curves are drawn once per answer into a canvas;
 * only the pulses and the rings move. */

#include "screen_apple.h"

#include <math.h>
#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);

#define LEFT 36
#define WIDTH 648
#define TOP 90
#define PLAN_H 420
#define GAP 12
#define ORB 88
#define OFFLINE 0xe0a23b
#define MESH 0xc3b9ff
#define MAX_LINKS 10
#define MAX_RINGS 8
#define PULSE 10

static lv_obj_t *pill, *pill_label, *bar, *bar_stripe, *bar_title, *bar_where;
static struct {
    lv_obj_t *box, *name, *orbs[4], *glyphs[4];
} rooms[3];
EXT_RAM_BSS_ATTR static desk_apple_t shown; /* off the LVGL task's small stack */

/* A link's curve in screen pixels: from a to b, bent through c. */
typedef struct {
    lv_obj_t *pulse;
    float ax, ay, cx, cy, bx, by;
} link_t;
typedef struct {
    lv_obj_t *ring;
    int32_t x, y; /* the orb's centre */
} ring_t;
static lv_obj_t *mesh;
static link_t links[MAX_LINKS];
static ring_t rings[MAX_RINGS];

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

static void centre(int room, int device, int32_t *x, int32_t *y)
{
    lv_area_t area;
    lv_obj_get_coords(rooms[room].orbs[device], &area);
    *x = (area.x1 + area.x2) / 2;
    *y = (area.y1 + area.y2) / 2;
}

static void point(const link_t *l, float t, float *x, float *y)
{
    float u = 1 - t;
    *x = u * u * l->ax + 2 * u * t * l->cx + t * t * l->bx;
    *y = u * u * l->ay + 2 * u * t * l->cy + t * t * l->by;
}

/* A pulse runs from one end to the other, fading in and out. */
static void run_pulse(void *var, int32_t at)
{
    link_t *l = var;
    float x, y;
    point(l, at / 1000.0f, &x, &y);
    lv_obj_set_pos(l->pulse, (int32_t)x - PULSE / 2, (int32_t)y - PULSE / 2);
    int32_t edge = at < 200 ? at : at > 800 ? 1000 - at : 200;
    lv_obj_set_style_bg_opa(l->pulse, (lv_opa_t)(edge * 255 / 200), 0);
    lv_obj_set_style_shadow_opa(l->pulse, (lv_opa_t)(edge * 200 / 200), 0);
}

static void grow_ring(void *var, int32_t at)
{
    ring_t *r = var;
    int32_t size = ORB + 70 * at / 1000;
    lv_obj_set_size(r->ring, size, size);
    lv_obj_set_pos(r->ring, r->x - size / 2, r->y - size / 2);
    lv_obj_set_style_border_opa(r->ring, (lv_opa_t)(170 * (1000 - at) / 1000), 0);
}

static void animate(void *var, lv_anim_exec_xcb_t exec, uint32_t ms, uint32_t delay, uint32_t pause)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, var);
    lv_anim_set_exec_cb(&anim, exec);
    lv_anim_set_values(&anim, 0, 1000);
    lv_anim_set_duration(&anim, ms);
    lv_anim_set_delay(&anim, delay);
    lv_anim_set_repeat_delay(&anim, pause);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_start(&anim);
}

/* One link: its curve into the canvas, and its pulse when it is up. */
static void add_link(lv_layer_t *layer, int *count, int ra, int da, int rb, int db)
{
    if (*count >= MAX_LINKS) {
        return;
    }
    const typeof(shown.rooms[0].device[0]) *a = &shown.rooms[ra].device[da], *b = &shown.rooms[rb].device[db];
    bool up = a->online && b->online && a->thread_ok && b->thread_ok;
    int32_t x0, y0, x1, y1;
    centre(ra, da, &x0, &y0);
    centre(rb, db, &x1, &y1);
    float dx = x1 - x0, dy = y1 - y0;
    float cx, cy;
    if (ra == rb) {
        /* Neighbours in one room sit close: an arch over them, so the link shows. */
        cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f - ORB;
    } else {
        /* Between rooms a gentle bend, always downwards, away from the rooms' names. */
        float px = -dy * 0.2f, py = dx * 0.2f;
        if (py < 0) {
            px = -px, py = -py;
        }
        cx = (x0 + x1) / 2.0f + px, cy = (y0 + y1) / 2.0f + py;
    }
    /* Each end stops short of its orb, along the way to the bend. */
    float r = ORB / 2.0f + 8, la = hypotf(cx - x0, cy - y0), lb = hypotf(cx - x1, cy - y1);
    link_t *l = &links[(*count)++];
    l->ax = x0 + (cx - x0) / (la > 1 ? la : 1) * r, l->ay = y0 + (cy - y0) / (la > 1 ? la : 1) * r;
    l->bx = x1 + (cx - x1) / (lb > 1 ? lb : 1) * r, l->by = y1 + (cy - y1) / (lb > 1 ? lb : 1) * r;
    l->cx = cx, l->cy = cy;

    lv_draw_line_dsc_t line;
    lv_draw_line_dsc_init(&line);
    /* Solid colours, mixed with the black beforehand: at part opacity the short segments'
     * overlapping ends showed as beads. */
    line.color = lv_color_hex(up ? 0x5f5a80 : 0x8a6a2f);
    line.width = 3;
    line.round_start = line.round_end = 1;
    const int steps = 32;
    float px, py;
    point(l, 0, &px, &py);
    for (int i = 1; i <= steps; i++) {
        float x, y;
        point(l, (float)i / steps, &x, &y);
        if (up || (i / 2) % 2 == 0) { /* broken: dashes, drawn by hand (LVGL dashes only straight lines) */
            line.p1.x = (int32_t)px - LEFT, line.p1.y = (int32_t)py - TOP;
            line.p2.x = (int32_t)x - LEFT, line.p2.y = (int32_t)y - TOP;
            lv_draw_line(layer, &line);
        }
        px = x, py = y;
    }
    if (up) {
        lv_obj_remove_flag(l->pulse, LV_OBJ_FLAG_HIDDEN);
        animate(l, run_pulse, 1600 + (int)hypotf(dx, dy) * 3, (*count) * 400, 1200);
    }
}

/* The nearest pair of routers between two rooms; false when either has none. */
static bool nearest(int ra, int rb, int *da, int *db)
{
    float best = 1e9f;
    for (int i = 0; i < shown.rooms[ra].devices; i++) {
        for (int j = 0; j < shown.rooms[rb].devices; j++) {
            if (!shown.rooms[ra].device[i].router || !shown.rooms[rb].device[j].router) {
                continue;
            }
            int32_t x0, y0, x1, y1;
            centre(ra, i, &x0, &y0);
            centre(rb, j, &x1, &y1);
            float d = hypotf(x1 - x0, y1 - y0);
            if (d < best) {
                best = d, *da = i, *db = j;
            }
        }
    }
    return best < 1e9f;
}

static void show_mesh(void)
{
    lv_obj_update_layout(lv_obj_get_screen(mesh));
    for (int i = 0; i < MAX_LINKS; i++) {
        lv_anim_delete(&links[i], run_pulse);
        lv_obj_add_flag(links[i].pulse, LV_OBJ_FLAG_HIDDEN);
    }
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(mesh);
    memset(buf->data, 0, buf->header.stride * PLAN_H);
    lv_layer_t layer;
    lv_canvas_init_layer(mesh, &layer);
    int count = 0;
    for (int r = 0; r < shown.count; r++) { /* a chain per room */
        int last = -1;
        for (int d = 0; d < shown.rooms[r].devices; d++) {
            if (!shown.rooms[r].device[d].router) {
                continue;
            }
            if (last >= 0) {
                add_link(&layer, &count, r, last, r, d);
            }
            last = d;
        }
    }
    for (int r = 1; r < shown.count; r++) { /* each room to the one before, and the last back */
        int da, db;
        if (nearest(r - 1, r, &da, &db)) {
            add_link(&layer, &count, r - 1, da, r, db);
        }
    }
    int da, db;
    if (shown.count > 2 && nearest(shown.count - 1, 0, &da, &db)) {
        add_link(&layer, &count, shown.count - 1, da, 0, db);
    }
    lv_canvas_finish_layer(mesh, &layer);
    lv_obj_invalidate(mesh);

    /* Ripples from what plays, two rings each, in the room's colour. */
    int n = 0;
    for (int i = 0; i < MAX_RINGS; i++) {
        lv_anim_delete(&rings[i], grow_ring);
        lv_obj_add_flag(rings[i].ring, LV_OBJ_FLAG_HIDDEN);
    }
    for (int r = 0; r < shown.count; r++) {
        for (int d = 0; d < shown.rooms[r].devices && n + 2 <= MAX_RINGS; d++) {
            if (!shown.rooms[r].device[d].plays) {
                continue;
            }
            for (int k = 0; k < 2; k++, n++) {
                ring_t *ring = &rings[n];
                centre(r, d, &ring->x, &ring->y);
                lv_obj_set_style_border_color(ring->ring, lv_color_hex(shown.rooms[r].glow ? shown.rooms[r].glow : MESH), 0);
                lv_obj_remove_flag(ring->ring, LV_OBJ_FLAG_HIDDEN);
                animate(ring, grow_ring, 2400, k * 1200, 0);
            }
        }
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
    ui_upper(caps, sizeof caps, shown.headline);
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
    show_mesh();
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

    lv_obj_t *header = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(header, 2, 0);
    lv_label_set_text(header, "APPLE DEVICES");
    lv_obj_set_pos(header, LEFT, 30);
    pill = ui_plain(screen);
    lv_obj_set_size(pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(pill, 16, 0);
    lv_obj_set_style_pad_ver(pill, 6, 0);
    lv_obj_set_style_radius(pill, 20, 0);
    lv_obj_set_style_bg_opa(pill, 50, 0);
    lv_obj_align(pill, LV_ALIGN_TOP_RIGHT, -LEFT, 22);
    pill_label = ui_text(pill, &instrument_24, 0xffffff);
    lv_obj_set_style_text_letter_space(pill_label, 1, 0);

    for (int i = 0; i < 3; i++) {
        lv_obj_t *box = rooms[i].box = ui_plain(screen);
        lv_obj_set_style_radius(box, 22, 0);
        lv_obj_set_style_border_width(box, 2, 0);
        lv_obj_set_style_shadow_width(box, 40, 0);
        rooms[i].name = ui_one_line(box, &instrument_28_bold, 0xb4b1c2, (WIDTH - GAP) / 2 - 48);
        lv_obj_set_pos(rooms[i].name, 22, 18);

        /* The devices, in a row in the middle of the room, under its name. */
        lv_obj_t *row = ui_plain(box);
        lv_obj_set_size(row, LV_PCT(100), ORB);
        lv_obj_align(row, LV_ALIGN_CENTER, 0, 26);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(row, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(row, 14, 0);
        for (int d = 0; d < 4; d++) {
            lv_obj_t *orb = rooms[i].orbs[d] = ui_plain(row);
            lv_obj_set_size(orb, ORB, ORB);
            lv_obj_set_style_radius(orb, LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_bg_opa(orb, LV_OPA_COVER, 0);
            lv_obj_set_style_border_width(orb, 3, 0);
            rooms[i].glyphs[d] = ui_plain(orb);
            lv_obj_set_style_bg_opa(rooms[i].glyphs[d], LV_OPA_COVER, 0);
        }
        lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);
    }

    /* The mesh over the plan (its lines stop short of the orbs), its pulses and the ripples. */
    mesh = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(mesh, lv_draw_buf_create(WIDTH, PLAN_H, LV_COLOR_FORMAT_ARGB8888, 0));
    memset(lv_canvas_get_draw_buf(mesh)->data, 0, lv_canvas_get_draw_buf(mesh)->header.stride * PLAN_H);
    lv_obj_set_pos(mesh, LEFT, TOP);
    lv_obj_remove_flag(mesh, LV_OBJ_FLAG_CLICKABLE);
    for (int i = 0; i < MAX_LINKS; i++) {
        lv_obj_t *pulse = links[i].pulse = ui_plain(screen);
        lv_obj_set_size(pulse, PULSE, PULSE);
        lv_obj_set_style_radius(pulse, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(pulse, lv_color_hex(MESH), 0);
        lv_obj_set_style_shadow_color(pulse, lv_color_hex(MESH), 0);
        lv_obj_set_style_shadow_width(pulse, 12, 0);
        lv_obj_add_flag(pulse, LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < MAX_RINGS; i++) {
        lv_obj_t *ring = rings[i].ring = ui_plain(screen);
        lv_obj_set_style_radius(ring, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(ring, 2, 0);
        lv_obj_add_flag(ring, LV_OBJ_FLAG_HIDDEN);
    }

    /* What plays, in a bar under the plan. */
    bar = ui_plain(screen);
    lv_obj_set_size(bar, WIDTH, 132);
    lv_obj_set_pos(bar, LEFT, TOP + PLAN_H + 24);
    lv_obj_set_style_radius(bar, 22, 0);
    lv_obj_set_style_clip_corner(bar, true, 0);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(bar, lv_color_hex(0x101015), 0);
    bar_stripe = ui_plain(bar);
    lv_obj_set_size(bar_stripe, 10, LV_PCT(100));
    lv_obj_set_style_bg_opa(bar_stripe, LV_OPA_COVER, 0);
    bar_title = ui_one_line(bar, &instrument_28_bold, 0xffffff, WIDTH - 72);
    lv_obj_set_pos(bar_title, 36, 28);
    bar_where = ui_one_line(bar, &instrument_24, 0xb4b1c2, WIDTH - 72);
    lv_obj_set_pos(bar_where, 36, 74);

    lv_timer_create(tick, 1000, NULL);
}
