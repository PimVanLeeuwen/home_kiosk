#pragma once

#include "cJSON.h"
#include "desk.h"

/* The Door panel's today view from the hub's answer (desk.c calls this). */
void desk_parse_door(const cJSON *screen, desk_door_t *door);
