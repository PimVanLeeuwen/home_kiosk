#pragma once

/* Builds the panel's screens and turns between them every few seconds; a touch
 * holds the current one for a minute. Call with the display lock held. */
void screens_start(void);

/* Holds the current screen for a minute, as a touch does (devshot's "hold"). */
void screens_hold(void);

/* Turns to the next screen now and holds it (devshot's "next"). Call with the
 * display lock held. */
void screens_next(void);
