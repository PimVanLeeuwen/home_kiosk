#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Alerts screen from the hub's answer (desk.c calls this). */
void desk_parse_alerts(const cJSON *screen, desk_alerts_t *alerts);
