#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Code screen from the hub's answer (desk.c calls this). */
void desk_parse_code(const cJSON *screen, desk_code_t *code);
