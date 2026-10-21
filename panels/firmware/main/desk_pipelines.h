#pragma once

#include "cJSON.h"
#include "desk.h"

/* The House panel's pipelines from the hub's answer (desk.c calls these). */
void desk_parse_run(const cJSON *screen, desk_pipeline_t *pipeline); /* one "pipeline" screen */
void desk_parse_pipelines(const cJSON *screen, desk_pipelines_t *pipelines); /* the idle card */
