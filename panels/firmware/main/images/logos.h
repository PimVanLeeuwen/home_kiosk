#pragma once

#include "lvgl.h"

/* The outside services' logos (images/make-logos.py), ended by a NULL key. */
typedef struct {
    const char *key;   /* the hub's service key: "github" */
    const lv_image_dsc_t *image; /* 48 px, alpha only: colour it on the panel */
    uint32_t glow;     /* the brand colour, or a soft white */
} logo_t;

extern const logo_t LOGOS[];
