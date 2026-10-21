#pragma once

#include <stdbool.h>
#include <stdint.h>

/* The panels run bright (the owner's choice); true black backgrounds keep the IPS
 * glow down. At 40 % the backlight of one board stayed off altogether. */
#define PANEL_BRIGHTNESS 100

/* Builds the panel's screens and turns between them every few seconds; a touch
 * holds the current one for a minute. Call with the display lock held. */
void screens_start(void);

/* Holds the current screen for a minute, as a touch does (devshot's "hold"). */
void screens_hold(void);

/* Turns to the next screen now and holds it (devshot's "next"). Call with the
 * display lock held. */
void screens_next(void);

/* For the health line (health.c): where the rotation is, and whether LVGL's
 * timers and drawing still run. */
typedef struct {
    int current, coming;
    bool waiting;
    uint32_t turns, beats, frames, touches;
    bool held; /* a touch holds the rotation */
} screens_state_t;
screens_state_t screens_state(void);

/* Swipe as a finger does: 1 for the next screen, -1 for the one before
 * (devshot's "swipe"). Call with the display lock held. */
void screens_swipe(int by);
