#pragma once

#include <stdbool.h>
#include <stdint.h>

#define DESK_RAIN_MAX 30

/* The clock screen's values from /api/desk/<name>, ready to draw. */
typedef struct {
    bool present;          /* the hub has answered at least once */
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

/* Asks the hub every 30 s once Wi-Fi is up; sets the system clock from it. */
void desk_start(void);
desk_clock_t desk_clock(void);
