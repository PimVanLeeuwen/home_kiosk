#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Tailnet screen from the hub's answer (desk.c calls this). */
void desk_parse_tailnet(const cJSON *screen, desk_tailnet_t *tailnet);
