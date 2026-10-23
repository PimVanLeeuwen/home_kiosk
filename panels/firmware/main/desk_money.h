#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Money screen from the hub's answer (desk.c calls this). */
void desk_parse_money(const cJSON *screen, desk_money_t *money);
