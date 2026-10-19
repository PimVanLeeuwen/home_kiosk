/* The rotation between a panel's screens (plan.md M16): a slow fade every
 * 10 s, held for a minute after a touch. A screen the hub has nothing for yet
 * is skipped. Only the Now panel's two screens so far. */

#include "screens.h"

#include "desk.h"
#include "lvgl.h"
#include "screen_clock.h"
#include "screen_day.h"

#define TURN_MS 10000
#define HOLD_MS 60000
#define FADE_MS 600

enum { CLOCK, DAY, COUNT };

static lv_obj_t *screens[COUNT];
static int current = CLOCK;
static uint32_t touched_at;
static bool touched;

static bool ready(int which)
{
    return which != DAY || desk_day().present;
}

static void advance(void)
{
    int next = current;
    do {
        next = (next + 1) % COUNT;
    } while (next != current && !ready(next));
    if (next != current) {
        current = next;
        lv_screen_load_anim(screens[current], LV_SCR_LOAD_ANIM_FADE_IN, FADE_MS, 0, false);
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
    screens[CLOCK] = lv_screen_active();
    screens[DAY] = lv_obj_create(NULL);
    screen_clock_create(screens[CLOCK]);
    screen_day_create(screens[DAY]);
    for (int i = 0; i < COUNT; i++) {
        lv_obj_add_event_cb(screens[i], on_touch, LV_EVENT_PRESSED, NULL);
    }
    lv_timer_create(turn, TURN_MS, NULL);
}
