#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Backups screen from the hub's answer (desk.c calls this). */
void desk_parse_backups(const cJSON *screen, desk_backups_t *backups);
