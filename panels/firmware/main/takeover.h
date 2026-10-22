#pragma once

#include <stdbool.h>

/* An open error over every screen (plan.md M16), until it is dismissed on this panel
 * or another: on LVGL's top layer, above the dark layer, so it reads with the lights
 * off. Call once after screens_start. */
void takeover_start(void);

/* Whether it shows now: the rotation and the dips stand still meanwhile. */
bool takeover_showing(void);
