/* The House panel's Media screen (plan.md M20, refocused 2026-10-12): what needs attention,
 * not what is being watched. Up to two downloads, each with its poster (chosen 2026-10-22),
 * title, what it is, a progress bar, how far and how long; then the missing episodes; and
 * the next to air at the bottom. With nothing downloading or missing: Up to date, and the
 * week ahead. Words from the hub (app/desk_media.py), posters from pictures.c. */

#include "screen_media.h"

#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define POSTER_W 96
#define POSTER_H 144
#define TEXT_X (POSTER_W + 22)
#define TEXT_W (WIDTH - TEXT_X)

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define VIOLET 0x7c6cf2
#define LILAC 0xc9c1ff

static lv_obj_t *sky, *title, *pill, *pill_text, *calm, *section, *section_side, *next;
static struct {
    lv_obj_t *box, *poster, *initial, *title, *detail, *bar, *left, *pct;
    ui_picture_t picture;
} downloads[DESK_MEDIA_DOWNLOADS];
static struct {
    lv_obj_t *box, *dot, *title, *episode, *line;
} rows[DESK_MEDIA_ROWS];
EXT_RAM_BSS_ATTR static desk_media_t shown; /* off the LVGL task's small stack */

static void show_downloads(void)
{
    for (int i = 0; i < DESK_MEDIA_DOWNLOADS; i++) {
        lv_obj_set_flag(downloads[i].box, LV_OBJ_FLAG_HIDDEN, i >= shown.download_count);
        if (i >= shown.download_count) {
            continue;
        }
        const typeof(shown.downloads[0]) *d = &shown.downloads[i];
        char first[2] = {d->title[0] ? d->title[0] : '?', '\0'};
        lv_label_set_text(downloads[i].initial, first);
        lv_label_set_text(downloads[i].title, d->title);
        lv_label_set_text(downloads[i].detail, d->detail);
        lv_bar_set_value(downloads[i].bar, d->progress, LV_ANIM_OFF);
        lv_obj_set_style_bg_color(downloads[i].bar, lv_color_hex(d->trouble ? AMBER : 0xb4a9ff), LV_PART_INDICATOR);
        lv_label_set_text(downloads[i].left, d->left);
        lv_obj_set_style_text_color(downloads[i].left, lv_color_hex(d->trouble ? AMBER : 0x8a8794), 0);
        lv_label_set_text(downloads[i].pct, d->pct);
    }
}

static void show_rows(void)
{
    bool missing = shown.missing_count > 0;
    int count = missing ? shown.missing_count : shown.week_count;
    lv_label_set_text(section, missing ? shown.missing_title : "THIS WEEK");
    lv_obj_set_style_text_color(section, lv_color_hex(missing ? AMBER : 0x8a8794), 0);
    lv_label_set_text(section_side, missing ? "Sonarr" : "");
    lv_obj_set_flag(lv_obj_get_parent(section), LV_OBJ_FLAG_HIDDEN, count == 0);
    for (int i = 0; i < DESK_MEDIA_ROWS; i++) {
        lv_obj_set_flag(rows[i].box, LV_OBJ_FLAG_HIDDEN, i >= count);
        if (i >= count) {
            continue;
        }
        lv_obj_set_style_bg_color(rows[i].dot, lv_color_hex(missing ? AMBER : VIOLET), 0);
        lv_label_set_text(rows[i].title, shown.rows[i].title);
        lv_label_set_text(rows[i].episode, shown.rows[i].episode);
        lv_label_set_text(rows[i].line, shown.rows[i].line);
    }
}

static void tick(lv_timer_t *timer)
{
    for (int i = 0; i < DESK_MEDIA_DOWNLOADS; i++) {
        ui_take_picture(PICTURE_POSTER + i, &downloads[i].picture);
    }
    static uint32_t version;
    if (desk_media_version() == version) {
        return;
    }
    desk_media_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    uint32_t tone = shown.tone == 'w' ? AMBER : shown.tone == 'b' ? LILAC : GREEN;
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(tone), 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(tone), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(shown.tone == 'w' ? AMBER : VIOLET), 0);
    lv_obj_set_flag(calm, LV_OBJ_FLAG_HIDDEN, shown.download_count > 0 || shown.missing_count > 0);
    show_downloads();
    show_rows();
    lv_label_set_text(next, shown.next);
    lv_obj_set_flag(next, LV_OBJ_FLAG_HIDDEN, shown.next[0] == '\0');
}

static void build_download(lv_obj_t *column, int i)
{
    lv_obj_t *box = downloads[i].box = ui_plain(column);
    lv_obj_set_size(box, WIDTH, POSTER_H);
    lv_obj_add_flag(box, LV_OBJ_FLAG_HIDDEN);

    /* The poster, over a violet tile with the title's first letter while it loads. */
    lv_obj_t *poster = downloads[i].poster = ui_plain(box);
    lv_obj_set_size(poster, POSTER_W, POSTER_H);
    lv_obj_set_style_radius(poster, 12, 0);
    lv_obj_set_style_clip_corner(poster, true, 0);
    lv_obj_set_style_bg_opa(poster, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(poster, lv_color_hex(0x2a2358), 0);
    lv_obj_set_style_bg_grad_color(poster, lv_color_hex(0x14121f), 0);
    lv_obj_set_style_bg_grad_dir(poster, LV_GRAD_DIR_VER, 0);
    downloads[i].initial = ui_text(poster, &instrument_40, 0xb4a9ff);
    lv_obj_center(downloads[i].initial);
    downloads[i].picture.image = lv_image_create(poster);
    lv_obj_add_flag(downloads[i].picture.image, LV_OBJ_FLAG_HIDDEN);

    downloads[i].title = ui_one_line(box, &instrument_28_bold, 0xf1eff7, TEXT_W);
    lv_obj_set_pos(downloads[i].title, TEXT_X, 6);
    downloads[i].detail = ui_one_line(box, &instrument_24, 0x8a8794, TEXT_W);
    lv_obj_set_pos(downloads[i].detail, TEXT_X, 46);
    lv_obj_t *bar = downloads[i].bar = lv_bar_create(box);
    lv_obj_set_size(bar, TEXT_W, 10);
    lv_obj_set_pos(bar, TEXT_X, 88);
    lv_bar_set_range(bar, 0, 1000);
    lv_obj_set_style_bg_color(bar, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(bar, 30, LV_PART_MAIN);
    lv_obj_set_style_radius(bar, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar, 5, LV_PART_INDICATOR);
    downloads[i].left = ui_one_line(box, &instrument_24, 0x8a8794, TEXT_W - 100);
    lv_obj_set_pos(downloads[i].left, TEXT_X, 108);
    downloads[i].pct = ui_text(box, &instrument_28_bold, 0xf1eff7);
    lv_obj_align(downloads[i].pct, LV_ALIGN_TOP_RIGHT, 0, 104);
}

void screen_media_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    sky = lv_image_create(screen);
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(VIOLET), 0);
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
    pill_text = ui_text(pill, &instrument_24, LILAC);
    lv_obj_set_style_text_letter_space(pill_text, 2, 0);

    /* Everything below the header in one column, so what is hidden leaves no gap. */
    lv_obj_t *column = ui_plain(screen);
    lv_obj_set_size(column, WIDTH, 590);
    lv_obj_set_pos(column, LEFT, 94);
    lv_obj_set_flex_flow(column, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(column, 18, 0);

    calm = ui_plain(column);
    lv_obj_set_size(calm, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_ver(calm, 20, 0);
    lv_obj_t *calm_words = ui_text(calm, &instrument_40, 0xffffff);
    lv_label_set_text(calm_words, "Up to date");
    lv_obj_t *calm_line = ui_text(calm, &instrument_24, 0x8a8794);
    lv_label_set_text(calm_line, "Nothing downloading, nothing missing");
    lv_obj_set_pos(calm_line, 0, 56);
    lv_obj_add_flag(calm, LV_OBJ_FLAG_HIDDEN);

    for (int i = 0; i < DESK_MEDIA_DOWNLOADS; i++) {
        build_download(column, i);
    }

    lv_obj_t *head = ui_plain(column);
    lv_obj_set_size(head, WIDTH, LV_SIZE_CONTENT);
    lv_obj_set_style_margin_top(head, 8, 0);
    section = ui_text(head, &instrument_24, AMBER);
    lv_obj_set_style_text_letter_space(section, 2, 0);
    section_side = ui_text(head, &instrument_24, 0x8a8794);
    lv_obj_align(section_side, LV_ALIGN_TOP_RIGHT, 0, 0);
    lv_obj_add_flag(head, LV_OBJ_FLAG_HIDDEN);
    for (int i = 0; i < DESK_MEDIA_ROWS; i++) {
        lv_obj_t *row = rows[i].box = ui_plain(column);
        lv_obj_set_size(row, WIDTH, 34);
        rows[i].dot = ui_plain(row);
        lv_obj_set_size(rows[i].dot, 12, 12);
        lv_obj_set_style_radius(rows[i].dot, 6, 0);
        lv_obj_set_style_bg_opa(rows[i].dot, LV_OPA_COVER, 0);
        lv_obj_align(rows[i].dot, LV_ALIGN_LEFT_MID, 2, 0);
        rows[i].title = ui_one_line(row, &instrument_28_bold, 0xf1eff7, 300);
        lv_obj_align(rows[i].title, LV_ALIGN_LEFT_MID, 28, 0);
        rows[i].episode = ui_one_line(row, &instrument_24, 0xb4b1c2, 90);
        lv_obj_align(rows[i].episode, LV_ALIGN_LEFT_MID, 340, 0);
        rows[i].line = ui_one_line(row, &instrument_24, 0x8a8794, 210);
        lv_obj_set_style_text_align(rows[i].line, LV_TEXT_ALIGN_RIGHT, 0);
        lv_obj_align(rows[i].line, LV_ALIGN_RIGHT_MID, 0, 0);
        lv_obj_add_flag(row, LV_OBJ_FLAG_HIDDEN);
    }

    next = ui_one_line(screen, &instrument_24, 0x7d7a8c, WIDTH);
    lv_obj_set_pos(next, LEFT, 650);
    lv_obj_add_flag(next, LV_OBJ_FLAG_HIDDEN);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
