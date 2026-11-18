#pragma once

#include "cJSON.h"
#include "desk.h"

/* The Now panel's Todos screen from the hub's answer (desk.c calls this). */
void desk_parse_todos(const cJSON *screen, desk_todos_t *todos);
