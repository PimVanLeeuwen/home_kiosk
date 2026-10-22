/* The House panel's running pipeline (plan.md M21), a job graph as in GitHub's run
 * view: one card per job in stage columns (a matrix job once, with ×N), joined by
 * curved lines as the workflow's `needs` say; below, the time so far (counted on
 * here from the hub's `since`), how long is left or how it ended, and the commit.
 * Two running pipelines take turns every 15 s. Layout of the cards from the hub's
 * columns and rows; wording and colours from the hub (app/desk_pipelines.py).
 *
 * The lines are painted into a transparent canvas when the answer changes: as
 * smooth curves they would be hundreds of shapes in one LVGL layer. */

#include "screen_pipeline.h"

#include <stdio.h>
#include <string.h>
#include <sys/time.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_time);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define TOP 104       /* the graph */
#define HEIGHT 400
#define COL_GAP 30
#define ROW_GAP 12
#define CARD_MAX 78     /* a card beside its icon */
#define NARROW 200      /* narrower cards put the icon on top, the name below */
#define TALL_MAX 124    /* ... and may be this tall: two lines of name and a progress line */
#define TURN_MS 15000 /* two pipelines take turns */

#define VIOLET 0x8f80ff
#define SOFT 0xb4a9ff
#define DIM 0x2c2a36
#define GREEN 0x3fb97f
#define RED 0xe5646a
#define AMBER 0xe0a23b

static lv_obj_t *sky, *canvas, *title, *number, *big, *first, *second, *commit, *meta;
static struct {
    lv_obj_t *card, *icon, *spinner, *name, *count, *time, *track, *bar;
} cards[DESK_PIPELINE_JOBS];
static struct {
    int x, y, w, h;
} boxes[DESK_PIPELINE_JOBS];
EXT_RAM_BSS_ATTR static desk_pipeline_t shown; /* off the LVGL task's small stack */
static int which;                                /* the run shown, when two take turns */
static uint32_t turned_at;

static bool is(const char *state, const char *word)
{
    return strcmp(state, word) == 0;
}

static desk_run_t *run(void)
{
    return &shown.runs[which < shown.count ? which : 0];
}

/* A job's own colour: green for a pipeline that shipped, else violet when done. */
static uint32_t job_colour(const char *state)
{
    if (is(state, "failed")) {
        return RED;
    }
    if (is(state, "approval")) {
        return AMBER;
    }
    if (is(state, "running")) {
        return SOFT;
    }
    if (is(state, "done")) {
        return is(run()->state, "success") ? GREEN : VIOLET;
    }
    return DIM;
}

/* The state icon: a filled circle with a check, a cross or "!", or a quiet ring. */
static void draw_icon(lv_event_t *event)
{
    lv_obj_t *icon = lv_event_get_target_obj(event);
    int i = (int)(intptr_t)lv_event_get_user_data(event);
    const char *state = run()->jobs[i].state;
    if (is(state, "running")) {
        return; /* its spinner */
    }
    lv_layer_t *layer = lv_event_get_layer(event);
    lv_area_t a;
    lv_obj_get_coords(icon, &a);
    int cx = (a.x1 + a.x2) / 2, cy = (a.y1 + a.y2) / 2;
    bool filled = is(state, "done") || is(state, "failed") || is(state, "approval");

    lv_draw_rect_dsc_t circle;
    lv_draw_rect_dsc_init(&circle);
    circle.radius = LV_RADIUS_CIRCLE;
    circle.bg_opa = filled ? LV_OPA_COVER : LV_OPA_TRANSP;
    circle.bg_color = lv_color_hex(job_colour(state));
    circle.border_width = filled ? 0 : 4;
    circle.border_color = lv_color_hex(DIM);
    lv_area_t round = {.x1 = cx - 13, .y1 = cy - 13, .x2 = cx + 13, .y2 = cy + 13};
    lv_draw_rect(layer, &circle, &round);
    if (!filled) {
        return;
    }

    lv_draw_line_dsc_t mark;
    lv_draw_line_dsc_init(&mark);
    mark.color = lv_color_black();
    mark.width = 3;
    mark.round_start = mark.round_end = 1;
    if (is(state, "done")) {
        mark.p1 = (lv_point_precise_t){cx - 6, cy};
        mark.p2 = (lv_point_precise_t){cx - 2, cy + 4};
        lv_draw_line(layer, &mark);
        mark.p1 = mark.p2;
        mark.p2 = (lv_point_precise_t){cx + 6, cy - 5};
        lv_draw_line(layer, &mark);
    } else if (is(state, "failed")) {
        mark.p1 = (lv_point_precise_t){cx - 5, cy - 5};
        mark.p2 = (lv_point_precise_t){cx + 5, cy + 5};
        lv_draw_line(layer, &mark);
        mark.p1 = (lv_point_precise_t){cx + 5, cy - 5};
        mark.p2 = (lv_point_precise_t){cx - 5, cy + 5};
        lv_draw_line(layer, &mark);
    } else {
        mark.p1 = (lv_point_precise_t){cx, cy - 6};
        mark.p2 = (lv_point_precise_t){cx, cy + 1};
        lv_draw_line(layer, &mark);
        mark.p1 = (lv_point_precise_t){cx, cy + 6};
        mark.p2 = (lv_point_precise_t){cx, cy + 6};
        lv_draw_line(layer, &mark);
    }
}

/* Where each card goes: stage columns side by side, rows centred in the graph's height. */
static void lay_out(void)
{
    desk_run_t *r = run();
    int columns = r->columns > 0 ? r->columns : 1;
    int rows[DESK_PIPELINE_JOBS] = {0};
    for (int i = 0; i < r->job_count; i++) {
        if (r->jobs[i].column < DESK_PIPELINE_JOBS && r->jobs[i].row + 1 > rows[r->jobs[i].column]) {
            rows[r->jobs[i].column] = r->jobs[i].row + 1;
        }
    }
    int w = (WIDTH - COL_GAP * (columns - 1)) / columns;
    int most = w < NARROW ? TALL_MAX : CARD_MAX;
    for (int i = 0; i < r->job_count; i++) {
        int c = r->jobs[i].column, n = rows[c] > 0 ? rows[c] : 1;
        int h = (HEIGHT - ROW_GAP * (n - 1)) / n;
        h = h > most ? most : h;
        int total = n * h + (n - 1) * ROW_GAP;
        boxes[i].x = LEFT + c * (w + COL_GAP);
        boxes[i].y = TOP + (HEIGHT - total) / 2 + r->jobs[i].row * (h + ROW_GAP);
        boxes[i].w = w;
        boxes[i].h = h;
    }
}

/* One pixel of the line canvas (ARGB8888, stored blue first), the stronger kept. */
static void paint(lv_draw_buf_t *buf, int x, int y, uint32_t colour, uint8_t alpha)
{
    if (x < 0 || x >= WIDTH || y < 0 || y >= HEIGHT) {
        return;
    }
    uint8_t *px = buf->data + y * buf->header.stride + x * 4;
    if (px[3] >= alpha) {
        return;
    }
    px[0] = colour & 0xff, px[1] = (colour >> 8) & 0xff, px[2] = (colour >> 16) & 0xff, px[3] = alpha;
}

/* The lines between the cards, as GitHub draws them: from a card's right edge to the
 * next one's left, an S-curve with its handles a gap's width out. */
static void draw_lines(void)
{
    lv_draw_buf_t *buf = lv_canvas_get_draw_buf(canvas);
    memset(buf->data, 0, buf->header.stride * HEIGHT);
    desk_run_t *r = run();
    for (int e = 0; e < r->edge_count; e++) {
        int a = r->edges[e][0], b = r->edges[e][1];
        const char *state = r->jobs[a].state;
        uint32_t colour = job_colour(state);
        uint8_t alpha = is(state, "done") ? 190 : 255;
        float x1 = boxes[a].x + boxes[a].w - LEFT, y1 = boxes[a].y + boxes[a].h / 2.0f - TOP;
        float x2 = boxes[b].x - LEFT, y2 = boxes[b].y + boxes[b].h / 2.0f - TOP;
        float hx = COL_GAP / 1.2f;
        int steps = (int)(x2 - x1 + (y2 > y1 ? y2 - y1 : y1 - y2)) + 2;
        for (int s = 0; s <= steps; s++) {
            float t = (float)s / steps, u = 1 - t;
            float x = u * u * u * x1 + 3 * u * u * t * (x1 + hx) + 3 * u * t * t * (x2 - hx) + t * t * t * x2;
            float y = u * u * u * y1 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y2;
            for (int dx = -1; dx <= 1; dx++) {
                for (int dy = -1; dy <= 1; dy++) {
                    paint(buf, (int)(x + 0.5f) + dx, (int)(y + 0.5f) + dy, colour, dx && dy ? alpha / 3 : alpha);
                }
            }
        }
    }
    lv_obj_invalidate(canvas);
}

static void show_cards(void)
{
    desk_run_t *r = run();
    lay_out();
    bool wide = r->columns <= 2; /* room for each job's time */
    for (int i = 0; i < DESK_PIPELINE_JOBS; i++) {
        lv_obj_set_flag(cards[i].card, LV_OBJ_FLAG_HIDDEN, i >= r->job_count);
        if (i >= r->job_count) {
            continue;
        }
        typeof(r->jobs[0]) *j = &r->jobs[i];
        bool running = is(j->state, "running"), loud = running || is(j->state, "failed") ||
                                                      is(j->state, "approval");
        lv_obj_set_pos(cards[i].card, boxes[i].x, boxes[i].y);
        lv_obj_set_size(cards[i].card, boxes[i].w, boxes[i].h);
        lv_obj_set_style_border_color(cards[i].card, lv_color_hex(loud ? job_colour(j->state) : DIM), 0);
        lv_obj_set_style_border_width(cards[i].card, loud ? 3 : 2, 0);
        lv_obj_set_flag(cards[i].spinner, LV_OBJ_FLAG_HIDDEN, !running);
        lv_obj_invalidate(cards[i].icon);
        lv_obj_set_flag(cards[i].count, LV_OBJ_FLAG_HIDDEN, j->count <= 1);
        lv_label_set_text_fmt(cards[i].count, "x%d", j->count);
        lv_label_set_text(cards[i].name, j->name);
        lv_obj_set_style_text_color(cards[i].name, lv_color_hex(is(j->state, "queued") ? 0x8a8794 : 0xffffff), 0);
        int line = lv_font_get_line_height(&instrument_24);
        bool stacked = boxes[i].w < NARROW && boxes[i].h >= 44 + 2 * line + 12;
        int name_width = stacked ? boxes[i].w - 24 : boxes[i].w - 58 - (wide && j->time[0] ? 70 : 0);
        int room = stacked ? 2 : (boxes[i].h >= 2 * line + 4 ? 2 : 1);
        lv_point_t size;
        lv_text_get_size(&size, j->name, &instrument_24, 0, 0, name_width, LV_TEXT_FLAG_NONE);
        int lines = (size.y + line - 1) / line;
        lines = lines < 1 ? 1 : lines > room ? room : lines;
        lv_obj_set_size(cards[i].name, name_width, lines * line);
        if (stacked) { /* the icon (and the count) on top, the name below */
            lv_obj_set_pos(cards[i].icon, 10, 8);
            lv_obj_set_pos(cards[i].count, 46, 10);
            lv_obj_set_pos(cards[i].name, 12, 42);
        } else {
            int icon_y = j->count > 1 ? boxes[i].h / 2 - 25 : boxes[i].h / 2 - 15;
            lv_obj_set_pos(cards[i].icon, 10, icon_y);
            lv_obj_set_pos(cards[i].count, 10, icon_y + 30);
            lv_obj_align(cards[i].name, LV_ALIGN_LEFT_MID, 46, 0);
        }
        lv_obj_set_flag(cards[i].time, LV_OBJ_FLAG_HIDDEN, !wide || !j->time[0]);
        lv_label_set_text(cards[i].time, j->time);
        lv_obj_set_style_text_color(cards[i].time, lv_color_hex(is(j->state, "failed") ? RED : 0x8a8794), 0);
        lv_obj_set_flag(cards[i].track, LV_OBJ_FLAG_HIDDEN, !running || j->progress <= 0);
        lv_obj_set_size(cards[i].track, boxes[i].w - 28, 4);
        lv_obj_set_size(cards[i].bar, (boxes[i].w - 28) * j->progress / 1000, 4);
    }
    draw_lines();
}

static void show_run(void)
{
    desk_run_t *r = run();
    uint32_t glow = is(r->state, "success") ? GREEN : is(r->state, "failure") ? RED
                    : is(r->state, "approval") ? AMBER : 0x7c6cf2;
    lv_obj_set_style_image_recolor(sky, lv_color_hex(glow), 0);
    lv_label_set_text(title, r->title);
    if (r->position[0]) {
        char text_up[32];
        snprintf(text_up, sizeof text_up, "%s · %s", r->number, r->position);
        for (char *p = text_up; *p; p++) {
            *p = (*p >= 'a' && *p <= 'z') ? *p - 32 : *p;
        }
        lv_label_set_text(number, text_up);
    } else {
        lv_label_set_text(number, r->number);
    }
    lv_obj_set_style_text_color(number, lv_color_hex(is(r->state, "running") ? 0x8a8794 : r->colour), 0);
    lv_label_set_text(big, r->big);
    lv_obj_set_style_text_color(big, lv_color_hex(is(r->state, "running") ? 0xffffff : r->colour), 0);
    lv_label_set_text(first, r->first);
    lv_label_set_text(second, r->second);
    lv_label_set_text(commit, r->commit);
    lv_label_set_text(meta, r->meta);
    show_cards();
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    bool changed = desk_pipeline_version() != version;
    if (changed) {
        desk_pipeline_copy(&shown);
        version = shown.version;
    }
    if (!shown.present) {
        return;
    }
    if (shown.count > 1 && lv_tick_elaps(turned_at) >= TURN_MS) {
        which = (which + 1) % shown.count;
        turned_at = lv_tick_get();
        changed = true;
    }
    if (which >= shown.count) {
        which = 0;
        changed = true;
    }
    if (changed) {
        show_run();
    }
    /* While it runs, the time counts on here between the hub's answers. */
    desk_run_t *r = run();
    struct timeval now;
    gettimeofday(&now, NULL);
    if (r->since > 0 && now.tv_sec > r->since && now.tv_sec > 1700000000) {
        long s = (long)(now.tv_sec - r->since);
        if (s >= 3600) {
            lv_label_set_text_fmt(big, "%ld:%02ld:%02ld", s / 3600, s / 60 % 60, s % 60);
        } else {
            lv_label_set_text_fmt(big, "%ld:%02ld", s / 60, s % 60);
        }
    }
}

void screen_pipeline_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x7c6cf2), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 80, 0);

    title = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);
    number = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_set_style_text_letter_space(number, 2, 0);
    lv_obj_align(number, LV_ALIGN_TOP_RIGHT, -LEFT, 30);

    canvas = lv_canvas_create(screen);
    lv_canvas_set_draw_buf(canvas, lv_draw_buf_create(WIDTH, HEIGHT, LV_COLOR_FORMAT_ARGB8888, 0));
    lv_obj_set_pos(canvas, LEFT, TOP);
    memset(lv_canvas_get_draw_buf(canvas)->data, 0, lv_canvas_get_draw_buf(canvas)->header.stride * HEIGHT);

    for (int i = 0; i < DESK_PIPELINE_JOBS; i++) {
        lv_obj_t *card = cards[i].card = ui_plain(screen);
        lv_obj_set_style_radius(card, 12, 0);
        lv_obj_set_style_bg_color(card, lv_color_hex(0x121119), 0);
        lv_obj_set_style_bg_opa(card, LV_OPA_COVER, 0);
        lv_obj_set_style_border_opa(card, LV_OPA_COVER, 0);
        cards[i].icon = ui_plain(card);
        lv_obj_set_size(cards[i].icon, 30, 30);
        lv_obj_add_event_cb(cards[i].icon, draw_icon, LV_EVENT_DRAW_MAIN, (void *)(intptr_t)i);
        cards[i].spinner = lv_spinner_create(cards[i].icon);
        lv_spinner_set_anim_params(cards[i].spinner, 1200, 90);
        lv_obj_set_size(cards[i].spinner, 26, 26);
        lv_obj_center(cards[i].spinner);
        lv_obj_set_style_arc_width(cards[i].spinner, 4, LV_PART_MAIN);
        lv_obj_set_style_arc_width(cards[i].spinner, 4, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(cards[i].spinner, lv_color_hex(DIM), LV_PART_MAIN);
        lv_obj_set_style_arc_color(cards[i].spinner, lv_color_hex(SOFT), LV_PART_INDICATOR);
        lv_obj_remove_flag(cards[i].spinner, LV_OBJ_FLAG_CLICKABLE);
        cards[i].count = ui_text(card, &instrument_24, 0xa7a7b4);
        cards[i].name = ui_text(card, &instrument_24, 0xffffff);
        lv_label_set_long_mode(cards[i].name, LV_LABEL_LONG_DOT);
        cards[i].time = ui_text(card, &instrument_24, 0x8a8794);
        lv_obj_align(cards[i].time, LV_ALIGN_RIGHT_MID, -16, 0);
        cards[i].track = ui_plain(card);
        lv_obj_set_style_bg_color(cards[i].track, lv_color_hex(DIM), 0);
        lv_obj_set_style_bg_opa(cards[i].track, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(cards[i].track, 2, 0);
        lv_obj_align(cards[i].track, LV_ALIGN_BOTTOM_LEFT, 14, -6);
        cards[i].bar = ui_plain(cards[i].track);
        lv_obj_set_style_bg_color(cards[i].bar, lv_color_hex(SOFT), 0);
        lv_obj_set_style_bg_opa(cards[i].bar, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(cards[i].bar, 2, 0);
        lv_obj_add_flag(card, LV_OBJ_FLAG_HIDDEN);
    }

    big = ui_text(screen, &instrument_time, 0xffffff);
    lv_obj_set_pos(big, LEFT - 4, 528);
    first = ui_text(screen, &instrument_28_bold, 0xa7a7b4);
    lv_obj_align(first, LV_ALIGN_TOP_RIGHT, -LEFT, 546);
    second = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_align(second, LV_ALIGN_TOP_RIGHT, -LEFT, 588);
    lv_obj_t *rule = ui_plain(screen);
    lv_obj_set_size(rule, WIDTH, 2);
    lv_obj_set_pos(rule, LEFT, 634);
    lv_obj_set_style_bg_color(rule, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(rule, 20, 0);
    commit = ui_text(screen, &instrument_24, 0xffffff);
    lv_label_set_long_mode(commit, LV_LABEL_LONG_DOT);
    lv_obj_set_size(commit, 430, lv_font_get_line_height(&instrument_24)); /* one line */
    lv_obj_set_pos(commit, LEFT, 652);
    meta = ui_text(screen, &instrument_24, 0x8a8794);
    lv_obj_align(meta, LV_ALIGN_TOP_RIGHT, -LEFT, 652);

    turned_at = lv_tick_get();
    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
