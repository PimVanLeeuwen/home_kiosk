/* The rotation between a panel's screens (plan.md M16): every 15 s, held for a
 * minute after a touch. The panel shows the screens the hub lists for it (the
 * board's own screen alone when it has no panel yet); a screen the hub has
 * nothing for yet is skipped, and one the hub no longer lists is left at once.
 * A board starts on the start-up screen and leaves it once the hub has answered.
 *
 * A panel that does not rotate right now (the hub's "rotate": false: Home while
 * music plays or every light is off) is swiped
 * instead, shows dots for its screens, and goes back to its first screen a
 * minute after the last touch. Every panel can be swiped.
 *
 * While every living room light is off (the hub's "dim") a dark layer lies over
 * every screen; it is laid on or lifted during the same dip through black, so
 * the change is as smooth as a turn. The backlight itself stays at its level:
 * one board went fully dark at 40 % during bring-up.
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
#include "screen_headlines.h"
#include "screen_apple.h"
#include "screen_laundry.h"
#include "screen_lights.h"
#include "screen_music.h"
#include "screen_playing.h"
#include "screen_start.h"
#include "screen_train.h"

#define TURN_MS 15000
#define HOLD_MS 60000
#define DIM_MS 250
#define DARKEN 165 /* how much the dark layer takes away, of 255 */

enum { CLOCK, TRAIN, AGENDA, DAY, HEADLINES, PLAYING, LIGHTS, LAUNDRY, APPLE, MUSIC, BOARD, START, COUNT };

static lv_obj_t *screens[COUNT];
static int current = START, coming = -1; /* coming: the screen being turned to */
static uint32_t touched_at;
static bool touched;
static bool waiting; /* for the new screen to be drawn */
static lv_obj_t *shade; /* the dark layer, on LVGL's top layer */
static lv_obj_t *dots;  /* where a swiped panel is, on LVGL's top layer */
static bool shaded;
static volatile uint32_t turns, beats, frames, touches; /* for the health line */

static void show_dots(void);

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
    case HEADLINES:
        return desk_has_headlines();
    case PLAYING:
        return desk_has_playing();
    case LIGHTS:
        return desk_has_lights();
    case LAUNDRY:
        return desk_has_laundry();
    case APPLE:
        return desk_has_apple();
    case MUSIC:
        return desk_has_music();
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
    show_dots();
    coming = -1;
}

/* The new screen is on the display: bring the light back. */
static void drawn(lv_event_t *event)
{
    frames++;
    if (waiting) {
        waiting = false;
        dim(0, PANEL_BRIGHTNESS, lit);
    }
}

static void dark(lv_anim_t *anim)
{
    waiting = true;
    if (shaded != desk_dim()) {
        shaded = !shaded;
        lv_obj_set_flag(shade, LV_OBJ_FLAG_HIDDEN, !shaded);
    }
    if (coming != current) {
        turns++;
        current = coming;
        lv_screen_load(screens[current]);
    } else {
        lv_obj_invalidate(lv_layer_top()); /* only the shade changed: draw once */
    }
}

/* Turn to the next screen with something to show (step 1) or the one before (-1). */
static void step(int by)
{
    if (coming >= 0) {
        return; /* already turning */
    }
    int next = current;
    do {
        next = (next + by + COUNT) % COUNT;
    } while (next != current && !ready(next));
    if (next != current) {
        coming = next;
        dim(PANEL_BRIGHTNESS, 0, dark);
    }
}

static void advance(void)
{
    step(1);
}

/* The dots of a swiped panel: one per screen it shows, the current one long. */
static void show_dots(void)
{
    lv_obj_clean(dots);
    int shown = 0;
    for (int i = 0; i < COUNT; i++) {
        if (i == START || !ready(i)) {
            continue;
        }
        shown++;
        lv_obj_t *dot = lv_obj_create(dots);
        lv_obj_remove_style_all(dot);
        lv_obj_set_size(dot, i == current ? 30 : 10, 10);
        lv_obj_set_style_radius(dot, 5, 0);
        lv_obj_set_style_bg_opa(dot, i == current ? 220 : 90, 0);
        lv_obj_set_style_bg_color(dot, lv_color_white(), 0);
    }
    lv_obj_set_flag(dots, LV_OBJ_FLAG_HIDDEN, desk_rotates() || shown < 2);
}

static int first_screen(void)
{
    for (int i = 0; i < COUNT; i++) {
        if (i != START && ready(i)) {
            return i;
        }
    }
    return current;
}

/* The hub changed this board's screens: leave one it no longer lists. Or the
 * living room lights went off or on: dip to lay the dark layer on or lift it. */
static void check(lv_timer_t *timer)
{
    /* Music starts on a swiped panel (Home), from a favourite on the panel or
     * anywhere else: go to Now Playing, as in the mockup. */
    static bool was_playing;
    bool playing = ready(PLAYING);
    bool started = playing && !was_playing;
    was_playing = playing;
    if (started && !desk_rotates() && coming < 0 && current != START && current != PLAYING) {
        coming = PLAYING;
        dim(PANEL_BRIGHTNESS, 0, dark);
        return;
    }
    if (coming < 0 && !ready(current)) {
        advance();
    } else if (coming < 0 && current != START && shaded != desk_dim()) {
        coming = current;
        dim(PANEL_BRIGHTNESS, 0, dark);
    }
}

static void turn(lv_timer_t *timer)
{
    if (touched && lv_tick_elaps(touched_at) < HOLD_MS) {
        return;
    }
    touched = false;
    if (desk_rotates()) {
        advance();
    } else if (coming < 0 && current != START && current != first_screen()) {
        coming = first_screen(); /* a swiped panel goes home after a quiet minute */
        dim(PANEL_BRIGHTNESS, 0, dark);
    }
}

/* A swipe left goes to the next screen, right to the one before. */
static void on_gesture(lv_event_t *event)
{
    lv_indev_t *indev = lv_indev_active();
    lv_dir_t dir = lv_indev_get_gesture_dir(indev);
    if (dir != LV_DIR_LEFT && dir != LV_DIR_RIGHT) {
        return;
    }
    lv_indev_wait_release(indev); /* a swipe over a tile is not also a tap on it */
    touched = true;
    touched_at = lv_tick_get();
    step(dir == LV_DIR_LEFT ? 1 : -1);
}

static void on_touch(lv_event_t *event)
{
    if (event) {
        touches++;
    }
    touched = true;
    touched_at = lv_tick_get();
}

static void beat(lv_timer_t *timer)
{
    beats++;
}

screens_state_t screens_state(void)
{
    return (screens_state_t){.current = current, .coming = coming, .waiting = waiting,
                             .turns = turns, .beats = beats, .frames = frames, .touches = touches,
                             .held = touched && lv_tick_elaps(touched_at) < HOLD_MS};
}

void screens_swipe(int by)
{
    touched = true;
    touched_at = lv_tick_get();
    step(by);
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
    screens[HEADLINES] = lv_obj_create(NULL);
    screens[PLAYING] = lv_obj_create(NULL);
    screens[LIGHTS] = lv_obj_create(NULL);
    screens[LAUNDRY] = lv_obj_create(NULL);
    screens[APPLE] = lv_obj_create(NULL);
    screens[MUSIC] = lv_obj_create(NULL);
    screens[BOARD] = lv_obj_create(NULL);
    screen_clock_create(screens[CLOCK]);
    screen_train_create(screens[TRAIN]);
    screen_agenda_create(screens[AGENDA]);
    screen_day_create(screens[DAY]);
    screen_headlines_create(screens[HEADLINES]);
    screen_playing_create(screens[PLAYING]);
    screen_lights_create(screens[LIGHTS]);
    screen_laundry_create(screens[LAUNDRY]);
    screen_apple_create(screens[APPLE]);
    screen_music_create(screens[MUSIC]);
    screen_board_create(screens[BOARD]);
    screen_start_create(screens[START]);
    for (int i = 0; i < COUNT; i++) {
        /* A panel screen never scrolls: anything past an edge is cut off, not
         * turned into a scrollbar. */
        lv_obj_remove_flag(screens[i], LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_scrollbar_mode(screens[i], LV_SCROLLBAR_MODE_OFF);
        /* A tap (press and release) holds the rotation; a press that never ends
         * (a case pressing on the edge) must not hold it for good. */
        lv_obj_add_event_cb(screens[i], on_touch, LV_EVENT_CLICKED, NULL);
        lv_obj_add_event_cb(screens[i], on_gesture, LV_EVENT_GESTURE, NULL);
    }
    /* Under the dark layer, so they dim with the rest. */
    dots = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(dots);
    lv_obj_set_size(dots, LV_SIZE_CONTENT, 10);
    lv_obj_align(dots, LV_ALIGN_BOTTOM_MID, 0, -14);
    lv_obj_set_flex_flow(dots, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(dots, 10, 0);
    lv_obj_remove_flag(dots, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_flag(dots, LV_OBJ_FLAG_HIDDEN);
    shade = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(shade);
    lv_obj_set_size(shade, LV_PCT(100), LV_PCT(100));
    lv_obj_set_style_bg_color(shade, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(shade, DARKEN, 0);
    lv_obj_remove_flag(shade, LV_OBJ_FLAG_CLICKABLE | LV_OBJ_FLAG_SCROLLABLE); /* taps go through */
    lv_obj_add_flag(shade, LV_OBJ_FLAG_HIDDEN);
    lv_display_add_event_cb(lv_display_get_default(), drawn, LV_EVENT_REFR_READY, NULL);
    lv_timer_create(turn, TURN_MS, NULL);
    lv_timer_create(check, 1000, NULL);
    lv_timer_create(beat, 1000, NULL);
}
