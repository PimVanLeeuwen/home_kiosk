/* The House panel's My sites screen (plan.md M20, tiles as chosen on 2026-10-21): a
 * tile per site in two columns, with its name, its response time (or how long it has
 * been down), the 30-day uptime below 100% and its 30 days as a strip. A site that is
 * down turns its tile red. Words from the hub (app/desk_sites.py).
 *
 * Each strip is painted into its own small canvas: 30 bars as LVGL shapes per tile
 * would be a few hundred in one layer, which stalls its task queue.
 *
 * Lifted (plan.md M27): each tile beats, a short line with one beat and a pulse running
 * along it while the site is up (flat and red when it is down). */

#include "screen_sites.h"

#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "arrive.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define TOP 96
#define GAP 14
#define TILE_W ((648 - GAP) / 2)
#define TILE_H 138
#define PAD 20
#define BAR 7
#define BAR_GAP 2
#define STRIP_W (DESK_SITE_DAYS * (BAR + BAR_GAP) - BAR_GAP)
#define STRIP_H 18

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define RED 0xff6b6b
#define TILE 0x0d0d10
#define TILE_DOWN 0x1f0c0d

typedef struct {
    lv_obj_t *box, *dot, *name, *left, *right, *strip, *trace, *beat;
    bool beating;
} tile_t;

/* The heartbeat (plan.md M27): one beat as a short line between the response time and the
 * uptime, and a bright pulse running along it while the site is up. */
#define TRACE_X 104
#define TRACE_W 104
#define TRACE_Y 74   /* its baseline, in the tile */
#define TRACE_H 13   /* how far the beat reaches */
#define BEAT_MS 40
#define BEAT_STEP 0.022f
static const float BEAT[][2] = {{0, 0},     {0.3f, 0},  {0.38f, -0.18f}, {0.44f, 0},   {0.5f, 0.25f},
                                {0.56f, -1}, {0.62f, 0.4f}, {0.68f, 0},   {0.8f, -0.3f}, {0.9f, 0}, {1, 0}};
#define BEAT_POINTS (sizeof BEAT / sizeof BEAT[0])

static lv_obj_t *self, *sky, *title, *pill, *pill_text;
static lv_point_precise_t trace_points[DESK_SITES][BEAT_POINTS];
static float beat_at;
static tile_t tiles[DESK_SITES];
EXT_RAM_BSS_ATTR static desk_sites_t shown; /* off the LVGL task's small stack */

/* A day's colour as painted over the tile: a healthy day a quiet green, a blip amber,
 * an outage red, and a day without a record barely there. */
static uint32_t day_colour(char day, bool down)
{
    switch (day) {
    case 'u':
        return 0x357658; /* GREEN at about 55% over the tile */
    case 'b':
        return AMBER;
    case 'd':
        return RED;
    default:
        return down ? 0x33201f : 0x1f1f25;
    }
}

static void paint_strip(lv_obj_t *canvas, const char *days, bool down)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    memset(buf->data, 0, buf->header.stride * STRIP_H);
    int count = strlen(days);
    for (int d = 0; d < count && d < DESK_SITE_DAYS; d++) {
        uint32_t colour = day_colour(days[d], down);
        for (int y = 0; y < STRIP_H; y++) {
            for (int x = 0; x < BAR; x++) {
                /* Clip the corners for a softly rounded bar. */
                bool corner = (x == 0 || x == BAR - 1) && (y == 0 || y == STRIP_H - 1);
                if (corner) {
                    continue;
                }
                uint8_t *px = buf->data + y * buf->header.stride + (d * (BAR + BAR_GAP) + x) * 4;
                px[0] = colour & 0xff, px[1] = (colour >> 8) & 0xff, px[2] = (colour >> 16) & 0xff, px[3] = 255;
            }
        }
    }
    lv_obj_invalidate(canvas);
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_sites_version() == version) {
        return;
    }
    desk_sites_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    bool any_down = shown.down > 0;
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    uint32_t pill_colour = any_down ? RED : GREEN;
    lv_obj_set_style_border_color(pill, lv_color_hex(pill_colour), 0);
    lv_obj_set_style_border_opa(pill, any_down ? LV_OPA_COVER : 150, 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(any_down ? 0xff8a8a : GREEN), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(any_down ? RED : 0x7c6cf2), 0);

    for (int i = 0; i < DESK_SITES; i++) {
        tile_t *t = &tiles[i];
        lv_obj_set_flag(t->box, LV_OBJ_FLAG_HIDDEN, i >= shown.count);
        if (i >= shown.count) {
            continue;
        }
        const typeof(shown.sites[0]) *site = &shown.sites[i];
        bool down = site->state == 'd';
        lv_obj_set_style_bg_color(t->box, lv_color_hex(down ? TILE_DOWN : TILE), 0);
        lv_obj_set_style_border_color(t->box, lv_color_hex(down ? 0x7a3333 : 0x1c1c22), 0);
        uint32_t dot = down ? RED : site->state == '?' ? 0x6c6a78 : GREEN;
        lv_obj_set_style_bg_color(t->dot, lv_color_hex(dot), 0);
        lv_label_set_text(t->name, site->name);
        lv_obj_set_style_text_color(t->name, lv_color_hex(down ? 0xff8a8a : 0xf1eff7), 0);
        lv_label_set_text(t->left, site->left);
        lv_obj_set_style_text_color(t->left, lv_color_hex(down ? 0xff8a8a : 0x8a8794), 0);
        lv_label_set_text(t->right, site->right);
        uint32_t worst = site->worst == 'd' ? RED : site->worst == 'b' ? AMBER : 0x8a8794;
        lv_obj_set_style_text_color(t->right, lv_color_hex(worst), 0);
        paint_strip(t->strip, site->days, down);
        /* Up: the beat in green; down or unknown: a flat line, red or grey. */
        t->beating = site->state != 'd' && site->state != '?';
        for (size_t p = 0; p < BEAT_POINTS; p++) {
            trace_points[i][p] = (lv_point_precise_t){TRACE_X + BEAT[p][0] * TRACE_W,
                                                      TRACE_Y + (t->beating ? BEAT[p][1] * TRACE_H : 0)};
        }
        lv_line_set_points(t->trace, trace_points[i], BEAT_POINTS);
        lv_obj_set_style_line_color(t->trace, lv_color_hex(down ? RED : t->beating ? GREEN : 0x6c6a78), 0);
    }
}

/* The pulses, together along every beating tile's line, while the screen shows. */
static void beat(lv_timer_t *timer)
{
    bool on = lv_screen_active() == self;
    beat_at += BEAT_STEP;
    if (beat_at > 1.4f) {
        beat_at = 0; /* a short rest between beats */
    }
    float at = beat_at > 1 ? 1 : beat_at;
    int seg = 0;
    while (seg < (int)BEAT_POINTS - 2 && BEAT[seg + 1][0] < at) {
        seg++;
    }
    float t0 = BEAT[seg][0], t1 = BEAT[seg + 1][0], f = t1 > t0 ? (at - t0) / (t1 - t0) : 0;
    float y = BEAT[seg][1] + (BEAT[seg + 1][1] - BEAT[seg][1]) * f;
    for (int i = 0; i < DESK_SITES; i++) {
        tile_t *t = &tiles[i];
        bool show = on && t->beating && i < shown.count && beat_at <= 1;
        lv_obj_set_flag(t->beat, LV_OBJ_FLAG_HIDDEN, !show);
        if (show) {
            lv_obj_set_pos(t->beat, TRACE_X + (int)(at * TRACE_W) - 4, TRACE_Y + (int)(y * TRACE_H) - 4);
        }
    }
}

void screen_sites_create(lv_obj_t *screen)
{
    self = screen;
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* House's quiet violet from the top; red while a site is down. */
    sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
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

    for (int i = 0; i < DESK_SITES; i++) {
        tile_t *t = &tiles[i];
        t->box = ui_plain(screen);
        lv_obj_set_size(t->box, TILE_W, TILE_H);
        lv_obj_set_pos(t->box, LEFT + (i % 2) * (TILE_W + GAP), TOP + (i / 2) * (TILE_H + GAP));
        lv_obj_set_style_radius(t->box, 18, 0);
        lv_obj_set_style_bg_opa(t->box, LV_OPA_COVER, 0);
        backdrops_glass(t->box);
        lv_obj_set_style_border_width(t->box, 1, 0);
        lv_obj_add_flag(t->box, LV_OBJ_FLAG_HIDDEN);

        t->dot = ui_plain(t->box);
        lv_obj_set_size(t->dot, 12, 12);
        lv_obj_set_style_radius(t->dot, 6, 0);
        lv_obj_set_style_bg_opa(t->dot, LV_OPA_COVER, 0);
        lv_obj_set_pos(t->dot, PAD, PAD + 11);
        t->name = ui_one_line(t->box, &instrument_28_bold, 0xf1eff7, TILE_W - PAD * 2 - 22);
        lv_obj_set_pos(t->name, PAD + 22, PAD);
        t->left = ui_text(t->box, &instrument_24, 0x8a8794);
        lv_obj_set_pos(t->left, PAD, 62);
        t->right = ui_text(t->box, &instrument_24, 0x8a8794);
        lv_obj_align(t->right, LV_ALIGN_TOP_RIGHT, -PAD, 62);

        t->trace = lv_line_create(t->box);
        lv_obj_set_style_line_width(t->trace, 2, 0);
        lv_obj_set_style_line_rounded(t->trace, true, 0);
        lv_obj_set_style_line_opa(t->trace, 200, 0);
        t->beat = ui_plain(t->box);
        lv_obj_set_size(t->beat, 8, 8);
        lv_obj_set_style_radius(t->beat, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(t->beat, lv_color_hex(0xe4fff1), 0);
        lv_obj_set_style_bg_opa(t->beat, LV_OPA_COVER, 0);
        lv_obj_set_style_shadow_width(t->beat, 14, 0);
        lv_obj_set_style_shadow_color(t->beat, lv_color_hex(GREEN), 0);
        lv_obj_set_style_shadow_opa(t->beat, 220, 0);
        lv_obj_add_flag(t->beat, LV_OBJ_FLAG_HIDDEN);
        t->strip = lv_canvas_create(t->box);
        lv_canvas_set_draw_buf(t->strip, lv_draw_buf_create(STRIP_W, STRIP_H, LV_COLOR_FORMAT_ARGB8888, 0));
        lv_obj_set_pos(t->strip, PAD, TILE_H - PAD - STRIP_H);
        arrive_draw_in(t->strip, STRIP_W, STRIP_H);
        memset(lv_canvas_get_draw_buf(t->strip)->data, 0, lv_canvas_get_draw_buf(t->strip)->header.stride * STRIP_H);
    }

    lv_timer_create(beat, BEAT_MS, NULL);
    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
