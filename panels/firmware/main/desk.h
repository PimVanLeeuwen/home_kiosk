#pragma once

#include <stdbool.h>
#include <stddef.h>
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
    char sun[24];          /* "Sunset 18:41", or "" */
    bool has_sky;          /* the hub's colour for the sky outside */
    uint32_t sky_colour;
    uint8_t sky_opacity;
    int rain_count;
    float rain[DESK_RAIN_MAX];
    char rain_axis[3][8];  /* under the bars: "Now", +1 h, +2 h */
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
        char id[20];          /* the hub's article id, for saving it */
        char title[160];
        char source[32];
        char age[12];         /* "12 min" */
        bool has_picture;
        bool saved;           /* saved to Readeck from a panel */
    } stories[DESK_STORIES];
} desk_headlines_t;

#define DESK_LIGHT_GROUPS 4
#define DESK_WHITES 6

/* The Home panel's lights: the living room's groups as tiles (app/desk_home.py). */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[32];          /* "Living room" */
    char count[32];          /* "5 of 5 lights on" */
    bool any_on;
    int group_count;
    struct {
        char id[16];
        char name[32];
        char line[48];       /* "3 lights · 3500 K · 80%" */
        bool on;
        int brightness;
        uint32_t tone;       /* the colour of its white, 0xrrggbb */
    } groups[DESK_LIGHT_GROUPS];
    bool has_whites;         /* the row of whites, for the group that has them */
    char whites_group[16];
    char whites_name[32];
    int whites_kelvin;       /* 0 when that group is off */
    int choice_count;
    struct {
        int kelvin;
        uint32_t tone;
    } choices[DESK_WHITES];
} desk_lights_t;

/* The Home panel's Now Playing (app/desk_home.py); its cover is picture slot 3. */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[96];
    char subtitle[96];
    bool has_cover;
    uint32_t colour;         /* the cover's main colour, for the light behind it */
    bool playing;            /* false: paused */
    int64_t progress_ms, duration_ms;
    double at;               /* when the progress was read, seconds since 1970 */
    char device[48];
} desk_playing_t;

#define DESK_FAVOURITES 4
#define PICTURE_PLAYING 3   /* picture slots: 0 to 2 the headlines, 3 the cover playing, */
#define PICTURE_FAVOURITE 4 /* 4 to 7 the favourites */

/* The Home panel's music: the favourites to start. */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char device[48];
    int count;
    struct {
        int position;
        char name[48];
        bool has_cover;
        uint32_t colour;
    } favourites[DESK_FAVOURITES];
    char last[128];          /* "Last played: ..." */
} desk_music_t;

/* The Home panel's laundry: the washer and dryer while one runs or is done. */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char headline[24];       /* "Washer running", "Done" */
    uint32_t headline_colour;
    int count;
    struct {
        char name[12];       /* "Washer" */
        char state[10];      /* running, paused, done, error, idle */
        uint32_t colour;     /* the ring's */
        uint32_t water;      /* the water's, in the door */
        int progress;        /* 0 to 1000 */
        int minutes;         /* left, or -1 */
        char line[48];       /* the program, or "Done at 09:41" */
        char status[48];     /* "Ready at 10:52", "Take it out" */
        uint32_t status_colour;
    } machines[2];
} desk_laundry_t;

/* The Home panel's Apple devices: the TVs and HomePods room by room, and what plays. */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char headline[16];       /* "All online", "1 offline" */
    uint32_t headline_colour;
    int count;
    struct {
        char name[24];
        uint32_t glow;       /* what plays there; 0 when nothing plays */
        int devices;
        struct {
            char kind[14];   /* tv, homepod, homepod_mini */
            bool online;
        } device[4];
    } rooms[3];
    bool has_playing;
    char title[96];          /* "Love Island · S12E16" */
    char where[64];          /* "Bedroom · paused · SenPlayer" */
    uint32_t playing_colour;
} desk_apple_t;

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
bool desk_dim(void); /* every living room light is off: the panel dims */
bool desk_rotates(void); /* the panel turns through its screens; Home is swiped */
bool desk_has_lights(void);
uint32_t desk_lights_version(void);
desk_lights_t desk_lights(void);
bool desk_has_playing(void);
uint32_t desk_playing_version(void);
desk_playing_t desk_playing(void);
bool desk_has_music(void);
bool desk_has_laundry(void);
uint32_t desk_laundry_version(void);
desk_laundry_t desk_laundry(void);
bool desk_has_apple(void);
uint32_t desk_apple_version(void);
desk_apple_t desk_apple(void);
uint32_t desk_music_version(void);
desk_music_t desk_music(void);

/* Ask the hub now instead of at the next half minute (after a change). */
void desk_poll_now(void);

/* A lights screen the hub answered a change with (actions.c): shown at once. */
void desk_take_lights(const char *json);
desk_headlines_t desk_headlines(void);
uint32_t desk_headlines_version(void); /* changes with every answer: copy only then */

/* This board's device key, "" until the hub has handed one over (it is kept
 * in the board's storage): what lets it save a story. */
void desk_key(char *into, size_t size);

/* This board's MAC address, "e8:f6:0a:e4:42:b0", as written on its back. */
const char *desk_mac(void);
