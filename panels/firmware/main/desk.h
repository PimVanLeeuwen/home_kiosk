#pragma once

#include <stdbool.h>
#include <stdint.h>

#define DESK_RAIN_MAX 30

/* The clock screen's values from /api/desk/<name>, ready to draw. */
typedef struct {
    bool present;          /* the hub has answered at least once */
    bool listed;           /* the clock is one of this panel's screens */
    bool stale;            /* the hub's weather is old */
    uint32_t version;      /* changes with every new answer */
    int utc_offset;        /* seconds east of UTC, now */
    char place[32];
    char date[24];
    bool has_temperature;
    int temperature;
    char description[48];
    int rain_count;
    float rain[DESK_RAIN_MAX];
    char rain_line[96];
    bool wet;
} desk_clock_t;

#define DESK_DAY_POINTS 19 /* 06:00 to 24:00 */

/* The day view's values: today until 20:00, then tomorrow. */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "Your day" or "Tomorrow" */
    int high, low;
    char lead[72];           /* "Rain likely from 14:00," */
    char rest[72];           /* "dry again from 17:00." */
    int count;
    float temperatures[DESK_DAY_POINTS];
    int rain[DESK_DAY_POINTS]; /* chance, % */
    char sunrise[6], sunset[6];
    int sunrise_minute, sunset_minute;
    bool today;              /* false: tomorrow, so no now line */
    char credit[24];
} desk_day_t;

/* A board's own screen: its MAC and what to do (no panel yet, or a panel
 * without screens yet). */
typedef struct {
    bool listed;
    uint32_t version;
    char mac[18];
    char title[40];
    char hint[80];
} desk_board_t;

/* Asks the hub every 30 s once Wi-Fi is up; sets the system clock from it. */
void desk_start(void);
desk_clock_t desk_clock(void);
desk_day_t desk_day(void);
desk_board_t desk_board(void);

/* This board's MAC address, "e8:f6:0a:e4:42:b0", as written on its back. */
const char *desk_mac(void);
