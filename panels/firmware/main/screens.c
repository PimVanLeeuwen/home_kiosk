/* The rotation between a panel's screens (plan.md M16): every 15 s, held for a
 * minute after a touch. The panel shows the screens the hub lists for it (the
 * board's own screen alone when it has no panel yet); a screen the hub has
 * nothing for yet is skipped, and one the hub no longer lists is left at once.
 * A board starts on the start-up screen and leaves it once the hub has answered.
 *
 * The turn dips through black with the backlight: down, the next screen swapped
 * in while it is dark, up again once that screen is drawn. A crossfade made
 * LVGL redraw and blend both whole screens per frame, about 6 frames a second
 * here; the backlight dims in hardware, so the dip is smooth and costs nothing. */

#include "screens.h"

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "desk.h"
#include "lvgl.h"
#include "screen_agenda.h"
#include "screen_board.h"
#include "screen_clock.h"
#include "screen_day.h"
#include "screen_start.h"
#include "screen_train.h"

#define TURN_MS 15000
#define HOLD_MS 60000
#define DIM_MS 250

enum { CLOCK, TRAIN, AGENDA, DAY, BOARD, START, COUNT };

static lv_obj_t *screens[COUNT];
static int current = START, coming = -1; /* coming: the screen being turned to */
static uint32_t touched_at;
static bool touched;
static bool waiting; /* for the new screen to be drawn */

static bool ready(int which)
{
    switch (which) {
    case START: /* until the hub has answered once */
        return !desk_clock().present;
    case CLOCK:
        return desk_clock().listed;
    case TRAIN:
        return desk_has_train();
    case AGENDA:
        return desk_has_agenda();
    case DAY:
        return desk_has_day();
    default:
        return desk_board().listed;
    }
}

static void set_light(void *unused, int32_t percent)
{
    bsp_display_brightness_set(percent);
}

static void dim(int32_t from, int32_t to, lv_anim_completed_cb_t done)
{
    lv_anim_t anim;
    lv_anim_init(&anim);
    lv_anim_set_exec_cb(&anim, set_light);
    lv_anim_set_values(&anim, from, to);
    lv_anim_set_duration(&anim, DIM_MS);
    lv_anim_set_path_cb(&anim, lv_anim_path_ease_in_out);
    lv_anim_set_completed_cb(&anim, done);
    lv_anim_start(&anim);
}

static void lit(lv_anim_t *anim)
{
    coming = -1;
}

/* The new screen is on the display: bring the light back. */
static void drawn(lv_event_t *event)
{
    if (waiting) {
        waiting = false;
        dim(0, PANEL_BRIGHTNESS, lit);
    }
}

static void dark(lv_anim_t *anim)
{
    current = coming;
    waiting = true;
    lv_screen_load(screens[current]);
}

static void advance(void)
{
    if (coming >= 0) {
        return; /* already turning */
    }
    int next = current;
    do {
        next = (next + 1) % COUNT;
    } while (next != current && !ready(next));
    if (next != current) {
        coming = next;
        dim(PANEL_BRIGHTNESS, 0, dark);
    }
}

/* The hub changed this board's screens: leave one it no longer lists. */
static void check(lv_timer_t *timer)
{
    if (coming < 0 && !ready(current)) {
        advance();
    }
}

static void turn(lv_timer_t *timer)
{
    if (touched && lv_tick_elaps(touched_at) < HOLD_MS) {
        return;
    }
    touched = false;
    advance();
}

static void on_touch(lv_event_t *event)
{
    touched = true;
    touched_at = lv_tick_get();
}

void screens_hold(void)
{
    on_touch(NULL);
}

void screens_next(void)
{
    screens_hold();
    advance();
}

void screens_start(void)
{
    screens[START] = lv_screen_active();
    screens[CLOCK] = lv_obj_create(NULL);
    screens[TRAIN] = lv_obj_create(NULL);
    screens[AGENDA] = lv_obj_create(NULL);
    screens[DAY] = lv_obj_create(NULL);
    screens[BOARD] = lv_obj_create(NULL);
    screen_clock_create(screens[CLOCK]);
    screen_train_create(screens[TRAIN]);
    screen_agenda_create(screens[AGENDA]);
    screen_day_create(screens[DAY]);
    screen_board_create(screens[BOARD]);
    screen_start_create(screens[START]);
    for (int i = 0; i < COUNT; i++) {
        lv_obj_add_event_cb(screens[i], on_touch, LV_EVENT_PRESSED, NULL);
    }
    lv_display_add_event_cb(lv_display_get_default(), drawn, LV_EVENT_REFR_READY, NULL);
    lv_timer_create(turn, TURN_MS, NULL);
    lv_timer_create(check, 1000, NULL);
}
