#pragma once

#include "cJSON.h"
#include "desk.h"

/* The Now panel's Briefing screen from the hub's answer (desk.c calls this). */
void desk_parse_briefing(const cJSON *screen, desk_briefing_t *briefing);
