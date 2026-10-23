#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's Media screen from the hub's answer (desk.c calls this); asks
 * pictures.c for the downloads' posters. */
void desk_parse_media(const cJSON *screen, desk_media_t *media);
