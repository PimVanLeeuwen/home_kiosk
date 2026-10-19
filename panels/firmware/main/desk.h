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

#define DESK_TRAIN_STOPS 6

typedef enum { DESK_TONE_UP, DESK_TONE_WARN, DESK_TONE_DOWN } desk_tone_t;

/* The Now panel's train screen: this weekday morning's train until it leaves,
 * or tomorrow's the evening before when it has a problem (app/desk_train.py). */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[48];          /* "Your train · direct" */
    char departure[6];       /* "07:16" */
    char departure_now[6];   /* the new time when late, else "" */
    bool gone;               /* it does not run: departure struck through */
    char status[64];         /* "On time", "6 min late", "Cancelled" */
    desk_tone_t tone;
    char sub[96];            /* "" when the panel words it from leaves_at */
    char platform[8];        /* "" when there is none to show */
    char platform_was[8];    /* the planned one when it changed, else "" */
    int64_t leaves_at;       /* seconds since 1970 of the followed train, 0 for none */
    char ring_label[16];
    int stop_count;
    struct {
        char time[6];
        char name[40];
        bool shifted, cancelled;
    } stops[DESK_TRAIN_STOPS];
    bool has_next;
    char next_departure[6], next_platform[8], next_arrives[6];
    bool has_notice;
    char notice_title[64];
    char notice_text[160];
} desk_train_t;

#define DESK_AGENDA_EVENTS 12
#define DESK_AGENDA_ALL_DAY 3

/* The Now panel's calendar screen: today's events (app/desk_agenda.py). */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[40];          /* "Today · Mon 19 Oct" */
    char count[16];          /* "5 events" */
    int event_count;
    struct {
        char title[64];
        char calendar[40];
        uint32_t color;      /* 0xrrggbb, the calendar's */
        int64_t start_at, end_at;      /* seconds since 1970 */
        int start_minute, end_minute;  /* local, for the ribbon */
        char start[6], end[6];         /* "09:30"; start "" when it began on an earlier day */
    } events[DESK_AGENDA_EVENTS];
    int all_day_count;
    struct {
        char title[64];
        uint32_t color;
    } all_day[DESK_AGENDA_ALL_DAY];
} desk_agenda_t;

#define DESK_STORIES 3

/* The Now panel's headlines: the lead story and two more (app/desk_headlines.py). */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    int count;
    struct {
        char title[160];
        char source[32];
        char age[12];         /* "12 min" */
        bool has_picture;
    } stories[DESK_STORIES];
} desk_headlines_t;

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
desk_train_t desk_train(void);
desk_agenda_t desk_agenda(void);

/* Whether the hub's answer has each screen, without copying its values: the
 * rotation asks every second, and some states are kilobytes (too much to copy
 * onto a task's stack). */
bool desk_has_day(void);
bool desk_has_train(void);
bool desk_has_agenda(void);
bool desk_has_headlines(void);
desk_headlines_t desk_headlines(void);
uint32_t desk_headlines_version(void); /* changes with every answer: copy only then */

/* This board's MAC address, "e8:f6:0a:e4:42:b0", as written on its back. */
const char *desk_mac(void);
