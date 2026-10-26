#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "cJSON.h"

/* The panels' pieces (plan.md M27, step 4): screens that are a painted picture from the hub
 * (its background) with a few words laid on it, as the hub places them, and the time where
 * the hub asks for it. One firmware screen (screen_piece.c) shows any of them. */

enum {
    PIECE_SKY, PIECE_NIGHT, PIECE_YEAR, PIECE_WEEK, PIECE_RADAR, PIECE_COUNTDOWN, PIECE_ART, PIECE_PHOTO, PIECE_ORBIT,
    PIECE_RUN, PIECE_RUNWEEK, PIECE_SESSION, /* plan.md M28: the last run, the week, the next session */
    PIECES
};

#define PIECE_LABELS 32 /* the week alone has 30 */
#define PIECE_PATH 64   /* the last run's route, for the light that runs it */

enum { PIECE_LEFT, PIECE_CENTRE, PIECE_RIGHT };

typedef struct {
    char text[96];
    int16_t x, y, width; /* x: the left edge, the middle or the right edge, by align */
    uint8_t font;        /* 0: 24, 1: 28 bold, 2: 40, 3: 52 bold, 4: the clock's 150, 5: 84 digits */
    uint8_t align;
    uint8_t lines;       /* at most; cut with "..." after */
    uint8_t spacing;     /* letter spacing, for the small capitals */
    uint32_t colour;
} piece_label_t;

typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    int label_count;
    piece_label_t labels[PIECE_LABELS];
    bool has_clock;      /* the panel's own time, "17:44", at `clock` */
    piece_label_t clock;
    int path_count;      /* points along a route, on the screen, in order */
    int16_t path[PIECE_PATH][2];
} desk_piece_t;

/* The hub's name for a piece ("sky"). */
const char *desk_piece_name(int which);

/* From desk.c's answer parsing: begin, offer every screen (true: it was a piece), commit. */
void desk_piece_begin(void);
bool desk_piece_parse(const cJSON *screen);
void desk_piece_commit(void);

bool desk_has_piece(int which);
uint32_t desk_piece_version(int which);
void desk_piece_copy(int which, desk_piece_t *out);
