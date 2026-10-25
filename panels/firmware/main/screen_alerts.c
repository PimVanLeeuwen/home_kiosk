/* The House panel's Alerts screen (plan.md M20, the design of 2026-10-10): the worst open
 * alert large, its icon pulsing slowly in amber or red, its severity, title, first lines
 * and how long it has been open, and up to three more below; when none is open, All
 * quiet with slow ripples round a green check, how long nothing has needed you and a
 * dot per day of this week. Words from the hub (app/desk_alerts.py).
 *
 * Only a few small objects move (the pulse, three rings), so LVGL redraws little. */

#include "screen_alerts.h"

#include <string.h>

#include "desk.h"
#include "esp_attr.h"
#include "lvgl.h"
#include "backdrops.h"
#include "ui.h"

LV_FONT_DECLARE(instrument_40);
LV_FONT_DECLARE(instrument_28_bold);
LV_FONT_DECLARE(instrument_24);
LV_IMAGE_DECLARE(glow_sky);

#define LEFT 36
#define WIDTH 648
#define ICON 112
#define CHECK 150
#define RIPPLE 340
#define RINGS 3

#define GREEN 0x5fd39c
#define AMBER 0xf0bd5a
#define RED 0xff6b6b

static lv_obj_t *sky, *title, *pill, *pill_text;
static lv_obj_t *open_box, *icon, *severity_pill, *severity, *hero_title, *hero_body, *hero_line, *divider;
static lv_obj_t *other_rows[DESK_ALERT_OTHERS], *other_dots[DESK_ALERT_OTHERS], *other_titles[DESK_ALERT_OTHERS];
static lv_obj_t *quiet_box, *rings[RINGS], *quiet_line, *day_dots[7], *day_letters[7];
EXT_RAM_BSS_ATTR static desk_alerts_t shown; /* off the LVGL task's small stack */

static uint32_t tone_colour(char tone)
{
    return tone == 'e' ? RED : tone == 'w' ? AMBER : GREEN;
}

static void pulse(void *obj, int32_t value)
{
    lv_obj_set_style_shadow_opa(obj, (lv_opa_t)value, 0);
}

/* A ring grows from the check outwards and fades as it goes. */
static void ripple(void *obj, int32_t at)
{
    int32_t size = CHECK + (RIPPLE - CHECK) * at / 1000;
    lv_obj_set_size(obj, size, size);
    lv_obj_set_style_border_opa(obj, (lv_opa_t)(140 * (1000 - at) / 1000), 0);
}

static void start(lv_obj_t *obj, lv_anim_exec_xcb_t exec, int32_t from, int32_t to, uint32_t ms,
                  uint32_t delay, bool back)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_var(&anim, obj);
    lv_anim_set_exec_cb(&anim, exec);
    lv_anim_set_values(&anim, from, to);
    lv_anim_set_duration(&anim, ms);
    lv_anim_set_delay(&anim, delay);
    lv_anim_set_repeat_count(&anim, LV_ANIM_REPEAT_INFINITE);
    if (back) {
        lv_anim_set_reverse_duration(&anim, ms);
    }
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_start(&anim);
}

static void show_open(void)
{
    uint32_t colour = tone_colour(shown.tone);
    lv_obj_set_style_border_color(icon, lv_color_hex(colour), 0);
    lv_obj_set_style_shadow_color(icon, lv_color_hex(colour), 0);
    lv_obj_set_style_bg_color(icon, lv_color_hex(shown.tone == 'e' ? 0x2a0f12 : 0x2a2010), 0);
    for (uint32_t i = 0; i < lv_obj_get_child_count(icon); i++) {
        lv_obj_set_style_bg_color(lv_obj_get_child(icon, i), lv_color_hex(colour), 0);
    }
    lv_obj_set_style_border_color(severity_pill, lv_color_hex(colour), 0);
    lv_obj_set_style_text_color(severity, lv_color_hex(colour), 0);
    lv_label_set_text(severity, shown.hero.severity);
    lv_label_set_text(hero_title, shown.hero.title);
    lv_label_set_text(hero_body, shown.hero.body);
    lv_label_set_text(hero_line, shown.hero.line);
    lv_obj_set_flag(divider, LV_OBJ_FLAG_HIDDEN, shown.other_count == 0);
    for (int i = 0; i < DESK_ALERT_OTHERS; i++) {
        lv_obj_set_flag(other_rows[i], LV_OBJ_FLAG_HIDDEN, i >= shown.other_count);
        if (i < shown.other_count) {
            lv_obj_set_style_bg_color(other_dots[i], lv_color_hex(tone_colour(shown.others[i].severity)), 0);
            lv_label_set_text(other_titles[i], shown.others[i].title);
        }
    }
}

static void show_quiet(void)
{
    lv_label_set_text(quiet_line, shown.quiet_line);
    for (int d = 0; d < 7; d++) {
        char letter[2] = {shown.days[d].letter, '\0'};
        lv_label_set_text(day_letters[d], letter);
        lv_obj_set_style_text_color(day_letters[d], lv_color_hex(shown.days[d].today ? 0xf1eff7 : 0x6c6a78), 0);
        char alert = shown.days[d].alert;
        uint32_t dot = alert ? tone_colour(alert) : shown.days[d].future ? 0x1a1920 : 0x2c2a33;
        lv_obj_set_style_bg_color(day_dots[d], lv_color_hex(dot), 0);
        lv_obj_set_style_border_width(day_dots[d], shown.days[d].today ? 2 : 0, 0);
    }
}

static void tick(lv_timer_t *timer)
{
    static uint32_t version;
    if (desk_alerts_version() == version) {
        return;
    }
    desk_alerts_copy(&shown);
    version = shown.version;
    if (!shown.present) {
        return;
    }
    uint32_t colour = tone_colour(shown.tone);
    lv_label_set_text(title, shown.title);
    lv_label_set_text(pill_text, shown.status);
    lv_obj_set_style_border_color(pill, lv_color_hex(colour), 0);
    lv_obj_set_style_text_color(pill_text, lv_color_hex(colour), 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(colour), 0);
    lv_obj_set_flag(open_box, LV_OBJ_FLAG_HIDDEN, !shown.has_hero);
    lv_obj_set_flag(quiet_box, LV_OBJ_FLAG_HIDDEN, shown.has_hero);
    if (shown.has_hero) {
        show_open();
    } else {
        show_quiet();
    }
}

static void build_open(lv_obj_t *screen)
{
    open_box = ui_plain(screen);
    lv_obj_set_size(open_box, WIDTH, 600);
    lv_obj_set_pos(open_box, LEFT, 100);
    lv_obj_add_flag(open_box, LV_OBJ_FLAG_HIDDEN);

    /* The icon: an exclamation mark in a rounded square that breathes in its colour. */
    icon = ui_plain(open_box);
    lv_obj_set_size(icon, ICON, ICON);
    lv_obj_set_style_radius(icon, 28, 0);
    lv_obj_set_style_bg_opa(icon, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(icon, 3, 0);
    lv_obj_set_style_shadow_width(icon, 40, 0);
    lv_obj_t *bar = ui_plain(icon);
    lv_obj_set_size(bar, 12, 42);
    lv_obj_set_style_radius(bar, 6, 0);
    lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
    lv_obj_align(bar, LV_ALIGN_CENTER, 0, -10);
    lv_obj_t *dot = ui_plain(icon);
    lv_obj_set_size(dot, 12, 12);
    lv_obj_set_style_radius(dot, 6, 0);
    lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
    lv_obj_align(dot, LV_ALIGN_CENTER, 0, 26);
    start(icon, pulse, 30, 170, 1600, 0, true);

    /* Beside it: the severity and the title, two lines at most. */
    severity_pill = ui_plain(open_box);
    lv_obj_set_size(severity_pill, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_pad_hor(severity_pill, 12, 0);
    lv_obj_set_style_pad_ver(severity_pill, 2, 0);
    lv_obj_set_style_radius(severity_pill, 16, 0);
    lv_obj_set_style_border_width(severity_pill, 2, 0);
    lv_obj_set_pos(severity_pill, ICON + 28, 0);
    severity = ui_text(severity_pill, &instrument_24, AMBER);
    lv_obj_set_style_text_letter_space(severity, 2, 0);
    hero_title = ui_text(open_box, &instrument_40, 0xffffff);
    lv_label_set_long_mode(hero_title, LV_LABEL_LONG_DOT);
    lv_obj_set_size(hero_title, WIDTH - ICON - 28, 2 * lv_font_get_line_height(&instrument_40));
    lv_obj_set_pos(hero_title, ICON + 28, 40);

    /* Under them: its first lines (three at most) and how long it has been open. */
    hero_body = ui_text(open_box, &instrument_24, 0xc9c6d6);
    lv_label_set_long_mode(hero_body, LV_LABEL_LONG_DOT);
    lv_obj_set_size(hero_body, WIDTH, 3 * lv_font_get_line_height(&instrument_24));
    lv_obj_set_pos(hero_body, 0, 150);
    hero_line = ui_one_line(open_box, &instrument_24, 0x8a8794, WIDTH);
    lv_obj_set_pos(hero_line, 0, 262);

    divider = ui_plain(open_box);
    lv_obj_set_size(divider, WIDTH, 1);
    lv_obj_set_pos(divider, 0, 330);
    lv_obj_set_style_bg_opa(divider, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(divider, lv_color_hex(0x2a2833), 0);
    for (int i = 0; i < DESK_ALERT_OTHERS; i++) {
        lv_obj_t *row = other_rows[i] = ui_plain(open_box);
        lv_obj_set_size(row, WIDTH, 52);
        lv_obj_set_pos(row, 0, 350 + i * 56);
        other_dots[i] = ui_plain(row);
        lv_obj_set_size(other_dots[i], 14, 14);
        lv_obj_set_style_radius(other_dots[i], 7, 0);
        lv_obj_set_style_bg_opa(other_dots[i], LV_OPA_COVER, 0);
        lv_obj_align(other_dots[i], LV_ALIGN_LEFT_MID, 2, 0);
        other_titles[i] = ui_one_line(row, &instrument_28_bold, 0xf1eff7, WIDTH - 32);
        lv_obj_align(other_titles[i], LV_ALIGN_LEFT_MID, 32, 0);
    }
}

static void build_quiet(lv_obj_t *screen)
{
    quiet_box = ui_plain(screen);
    lv_obj_set_size(quiet_box, 720, 620);
    lv_obj_set_pos(quiet_box, 0, 90);
    lv_obj_add_flag(quiet_box, LV_OBJ_FLAG_HIDDEN);

    /* Rings that grow from the check outwards, one after another. */
    lv_obj_t *field = ui_plain(quiet_box);
    lv_obj_set_size(field, RIPPLE, RIPPLE);
    lv_obj_align(field, LV_ALIGN_TOP_MID, 0, 0);
    for (int i = 0; i < RINGS; i++) {
        rings[i] = ui_plain(field);
        lv_obj_set_size(rings[i], CHECK, CHECK);
        lv_obj_set_style_radius(rings[i], LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_border_width(rings[i], 2, 0);
        lv_obj_set_style_border_color(rings[i], lv_color_hex(GREEN), 0);
        lv_obj_set_style_border_opa(rings[i], 0, 0);
        lv_obj_center(rings[i]);
        start(rings[i], ripple, 0, 1000, 4200, i * 1400, false);
    }

    lv_obj_t *check = ui_plain(field);
    lv_obj_set_size(check, CHECK, CHECK);
    lv_obj_center(check);
    lv_obj_set_style_radius(check, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_opa(check, LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(check, lv_color_hex(0x10241b), 0);
    lv_obj_set_style_border_width(check, 3, 0);
    lv_obj_set_style_border_color(check, lv_color_hex(0x2f6b50), 0);
    static lv_point_precise_t tick_points[] = {{44, 78}, {66, 100}, {108, 54}};
    lv_obj_t *mark = lv_line_create(check);
    lv_line_set_points(mark, tick_points, 3);
    lv_obj_set_style_line_width(mark, 10, 0);
    lv_obj_set_style_line_rounded(mark, true, 0);
    lv_obj_set_style_line_color(mark, lv_color_hex(GREEN), 0);

    lv_obj_t *words = ui_text(quiet_box, &instrument_40, 0xffffff);
    lv_label_set_text(words, "All quiet");
    lv_obj_align(words, LV_ALIGN_TOP_MID, 0, RIPPLE + 6);
    quiet_line = ui_one_line(quiet_box, &instrument_24, 0x8a8794, WIDTH);
    lv_obj_set_style_text_align(quiet_line, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(quiet_line, LV_ALIGN_TOP_MID, 0, RIPPLE + 62);

    /* This week: a dot per day, lit amber or red on a day that had an alert. */
    for (int d = 0; d < 7; d++) {
        int x = 360 - 3 * 64 + d * 64;
        day_dots[d] = ui_plain(quiet_box);
        lv_obj_set_size(day_dots[d], 18, 18);
        lv_obj_set_style_radius(day_dots[d], 9, 0);
        lv_obj_set_style_bg_opa(day_dots[d], LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(day_dots[d], lv_color_hex(0xf1eff7), 0);
        lv_obj_set_pos(day_dots[d], x - 9, RIPPLE + 122);
        day_letters[d] = ui_text(quiet_box, &instrument_24, 0x6c6a78);
        lv_obj_set_width(day_letters[d], 40);
        lv_obj_set_style_text_align(day_letters[d], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_pos(day_letters[d], x - 20, RIPPLE + 150);
    }
}

void screen_alerts_create(lv_obj_t *screen)
{
    lv_obj_set_style_bg_color(screen, lv_color_black(), 0);

    /* Green from the top while all is quiet; amber or red with an open alert. */
    sky = lv_image_create(screen);
    backdrops_aside(sky); /* the hub's painted light instead (plan.md M27) */
    lv_image_set_src(sky, &glow_sky);
    lv_image_set_pivot(sky, 0, 0);
    lv_image_set_scale(sky, 512);
    lv_obj_set_pos(sky, 0, 0);
    lv_obj_set_style_image_recolor(sky, lv_color_hex(GREEN), 0);
    lv_obj_set_style_image_recolor_opa(sky, LV_OPA_COVER, 0);
    lv_obj_set_style_image_opa(sky, 50, 0);

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

    build_open(screen);
    build_quiet(screen);

    lv_timer_create(tick, 1000, NULL);
    tick(NULL);
}
