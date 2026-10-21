#pragma once

#include "lvgl.h"

/* The House panel's running pipeline as a job graph (two take turns). */
void screen_pipeline_create(lv_obj_t *screen);
