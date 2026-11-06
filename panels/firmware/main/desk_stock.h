#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Stock screen from the hub's answer (desk.c calls this). */
void desk_parse_stock(const cJSON *screen, desk_stock_t *stock);
