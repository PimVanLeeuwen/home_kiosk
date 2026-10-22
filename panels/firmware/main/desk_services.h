#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Services screen from the hub's answer (desk.c calls this). */
void desk_parse_services(const cJSON *screen, desk_services_t *services);
