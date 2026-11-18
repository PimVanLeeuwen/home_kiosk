/* The Now panel's Todos screen (plan.md M37): the open todos in the hub's order (High,
 * then due date, then oldest), four large rows a page. With more than four the page turns
 * every 8 s with a short fade of the text alone (no layer), and dots by the header show
 * which page is up, as on the Door panel's reminders. Read-only: ticking off stays in the
 * hub. Words from the hub (app/desk_todos.py); the panel only places them.
 *
 * Its light: the violet glow from the top turns red while a todo is overdue. */

#include "screen_todos.h"

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define ROWS 4
#define PAGES ((DESK_TODOS + ROWS - 1) / ROWS)
#define ROWS_TOP 92
#define ROW_HEIGHT 128
#define ROW_GAP 14
#define RING 30
#define TEXT_X 80
#define TAG_WIDTH 76
#define PAGE_MS 8000
#define FADE_MS 220
#define DOT 8

#define GREY 0x8a8794
#define FAINT 0x6c6a78
#define WHITE 0xf2f1f6
#define VIOLET 0x9d8cff
#define RED 0xff6b6b
#define AMBER 0xf0bd5a

static lv_obj_t *sky, *title, *dots[PAGES], *rows[ROWS], *rings[ROWS], *titles[ROWS];
static lv_obj_t *tags[ROWS], *dues[ROWS], *more;
EXT_RAM_BSS_ATTR static desk_todos_t shown; /* off the LVGL task's small stack */
static int page; /* the page on screen */

static uint32_t due_colour(char state)
{
    return state == 'o' ? RED : state == 't' ? VIOLET : GREY;
}

/* One page of the todos, and the dots that say which. */
static void show_page(void)
{
    int pages = (shown.count + ROWS - 1) / ROWS;
    if (page >= pages) {
        page = 0;
    }
    for (int i = 0; i < ROWS; i++) {
        int at = page * ROWS + i;
        bool on = at < shown.count;
        lv_obj_set_flag(rows[i], LV_OBJ_FLAG_HIDDEN, !on);
        if (!on) {
            continue;
        }
        const typeof(shown.todos[0]) *t = &shown.todos[at];
        bool second = t->high || t->due[0] != '\0';
        lv_label_set_text(titles[i], t->title);
        /* A title alone sits in the middle; with High or a due date, on top of them. */
        lv_obj_align(titles[i], second ? LV_ALIGN_TOP_LEFT : LV_ALIGN_LEFT_MID, TEXT_X, second ? 20 : 0);
        lv_obj_set_flag(tags[i], LV_OBJ_FLAG_HIDDEN, !t->high);
        lv_label_set_text(dues[i], t->due);
        lv_obj_set_style_text_color(dues[i], lv_color_hex(due_colour(t->state)), 0);
        lv_obj_set_x(dues[i], TEXT_X + (t->high ? TAG_WIDTH + 14 : 0));
        lv_obj_set_style_border_color(rows[i], lv_color_hex(t->state == 'o' ? 0x4a2328 : 0x26232f), 0);
    }
    /* Past the twelve the hub sends: a line under the last page. */
    lv_obj_set_flag(more, LV_OBJ_FLAG_HIDDEN, shown.more == 0 || page != pages - 1);
    lv_label_set_text_fmt(more, "and %d more", shown.more);
    for (int i = 0; i < PAGES; i++) {
        lv_obj_set_flag(dots[i], LV_OBJ_FLAG_HIDDEN, pages < 2 || i >= pages);
        lv_obj_set_style_bg_opa(dots[i], i == page ? LV_OPA_COVER : 70, 0);
    }
}

/* The fade sets the text's and the tags' own opacity, so no layer is drawn. */
static void set_rows_opa(void *unused, int32_t opa)
{
    (void)unused;
    for (int i = 0; i < ROWS; i++) {
        lv_obj_set_style_text_opa(titles[i], opa, 0);
        lv_obj_set_style_text_opa(dues[i], opa, 0);
        lv_obj_set_style_text_opa(tags[i], opa, 0);
        lv_obj_set_style_bg_opa(tags[i], opa * 40 / 255, 0);
        lv_obj_set_style_border_opa(rings[i], opa, 0);
    }
    lv_obj_set_style_text_opa(more, opa, 0);
}

static void fade(int32_t from, int32_t to, lv_anim_completed_cb_t done)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, rows); /* any key: one fade at a time */
    lv_anim_set_exec_cb(&anim, (lv_anim_exec_xcb_t)set_rows_opa);
    lv_anim_set_values(&anim, from, to);
    lv_anim_set_duration(&anim, FADE_MS);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_set_completed_cb(&anim, done);
    lv_anim_start(&anim);
}

static void faded_out(lv_anim_t *anim)
{
    (void)anim;
    page++;
    show_page();
    fade(LV_OPA_TRANSP, LV_OPA_COVER, NULL);
}

static void turn_page(lv_timer_t *timer)
{
    (void)timer;
    if (shown.present && shown.count > ROWS) {
        fade(LV_OPA_COVER, LV_OPA_TRANSP, faded_out);
    }
}

static void tick(lv_timer_t *timer)
{
    (void)timer;
    static uint32_t version;
    if (desk_todos_version() == version) {
        return;
    }
    desk_todos_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    lv_label_set_text(title, shown.title);
    bool late = false;
    for (int i = 0; i < shown.count; i++) {
        late = late || shown.todos[i].state == 'o';
    }
    lv_obj_set_style_image_recolor(sky, lv_color_hex(late ? 0xe0565b : 0x8f7cf6), 0);
    show_page();
}

void screen_todos_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Violet from the top, as on Briefing; red while a todo is overdue. */
    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(0x8f7cf6), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 80, 0);

    title = ui_text(screen, &instrument_24, GREY);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, LEFT, 30);

    for (int i = 0; i < PAGES; i++) {
        dots[i] = ui_plain(screen);
        lv_obj_set_size(dots[i], DOT, DOT);
        lv_obj_set_pos(dots[i], LEFT + WIDTH - (PAGES - i) * 2 * DOT + DOT, 40);
        lv_obj_set_style_radius(dots[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(dots[i], lv_color_hex(VIOLET), 0);
        lv_obj_add_flag(dots[i], LV_OBJ_FLAG_HIDDEN);
    }

    for (int i = 0; i < ROWS; i++) {
        lv_obj_t *row = rows[i] = ui_plain(screen);
        lv_obj_set_size(row, WIDTH, ROW_HEIGHT);
        lv_obj_set_pos(row, LEFT, ROWS_TOP + i * (ROW_HEIGHT + ROW_GAP));
        lv_obj_set_style_radius(row, 20, 0);
        lv_obj_set_style_bg_color(row, lv_color_hex(0x15141c), 0);
        lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(row, lv_color_hex(0x26232f), 0);
        lv_obj_set_style_border_width(row, 1, 0);
        lv_obj_add_flag(row, LV_OBJ_FLAG_HIDDEN);

        /* An empty ring, as in the hub: a todo to tick off there. */
        rings[i] = ui_plain(row);
        lv_obj_set_size(rings[i], RING, RING);
        lv_obj_align(rings[i], LV_ALIGN_LEFT_MID, 26, 0);
        lv_obj_set_style_radius(rings[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_color(rings[i], lv_color_hex(0x55525f), 0);
        lv_obj_set_style_border_width(rings[i], 2, 0);

        titles[i] = ui_one_line(row, &instrument_40, WHITE, WIDTH - TEXT_X - 28);

        tags[i] = ui_text(row, &instrument_24, AMBER);
        lv_label_set_text(tags[i], "HIGH");
        lv_obj_set_style_text_letter_space(tags[i], 2, 0);
        lv_obj_set_style_text_align(tags[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(tags[i], TAG_WIDTH);
        lv_obj_set_style_pad_ver(tags[i], 2, 0);
        lv_obj_set_style_radius(tags[i], 6, 0);
        lv_obj_set_style_bg_color(tags[i], lv_color_hex(AMBER), 0);
        lv_obj_set_style_bg_opa(tags[i], 40, 0);
        lv_obj_set_pos(tags[i], TEXT_X, 74);
        lv_obj_add_flag(tags[i], LV_OBJ_FLAG_HIDDEN);

        dues[i] = ui_text(row, &instrument_24, GREY);
        lv_obj_set_pos(dues[i], TEXT_X, 76);
    }

    more = ui_text(screen, &instrument_24, FAINT);
    lv_obj_set_pos(more, LEFT + 20, ROWS_TOP + ROWS * (ROW_HEIGHT + ROW_GAP) - 2);
    lv_obj_add_flag(more, LV_OBJ_FLAG_HIDDEN);

    lv_timer_create(tick, 1000, NULL);
    lv_timer_create(turn_page, PAGE_MS, NULL);
    tick(NULL);
}
