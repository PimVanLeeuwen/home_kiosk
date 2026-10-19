#pragma once

#include <stdbool.h>

/* Updates over Wi-Fi from the hub (plan.md M16): checks every 10 minutes and
 * installs a different firmware between 04:00 and 05:00, then restarts. A new
 * firmware that cannot reach the hub within 5 minutes goes back to the old one. */
void update_start(void);

/* The hub answered: a new firmware works, so keep it. */
void update_hub_answered(void);

/* True while a new firmware is written to flash: other network use waits. */
bool update_busy(void);

/* Check and install now, whatever the hour: "update" on the console, or the
 * hub's "Update now" (Settings, Desk panels). */
void update_now(void);
