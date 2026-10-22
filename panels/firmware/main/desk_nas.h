#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's NAS screen from the hub's answer (desk.c calls this). */
void desk_parse_nas(const cJSON *screen, desk_nas_t *nas);
