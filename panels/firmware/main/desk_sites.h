#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's My sites screen from the hub's answer (desk.c calls this). */
void desk_parse_sites(const cJSON *screen, desk_sites_t *sites);
