#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Top movers screen from the hub's answer (desk.c calls this). */
void desk_parse_movers(const cJSON *screen, desk_movers_t *movers);
