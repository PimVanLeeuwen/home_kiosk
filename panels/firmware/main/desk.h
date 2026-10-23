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
    /* The Horizon clock (2026-10-23): the sky's three colours, zenith to horizon, the sun
     * or the moon and how far along its arc (0..1000), the moon's phase (0 new, 500 full). */
    bool has_horizon;
    uint32_t sky_top, sky_mid, sky_low;
    bool moon;               /* the moon, not the sun */
    int at;
    int moon_phase;
    bool veiled;             /* behind clouds: dimmer */
    bool stars;
    char rise[8], set[8];    /* "08:06", "18:37" */
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
#define DESK_AGENDA_TOMORROW 3

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
    /* Once today has nothing left (or had nothing), tomorrow's first events (2026-10-23). */
    bool tomorrow_mode;
    char today_line[24];     /* "Nothing more today", "Nothing today" */
    char tomorrow_title[40]; /* "Tomorrow · Tue 20 Oct" */
    int tomorrow_count;
    struct {
        char title[64];
        char calendar[40];
        uint32_t color;
        char start[6], end[6];
    } tomorrow[DESK_AGENDA_TOMORROW];
    int tomorrow_all_day_count;
    struct {
        char title[64];
        uint32_t color;
    } tomorrow_all_day[2];
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
#define PICTURE_FAVOURITE 4 /* 4 to 7 the favourites, */
#define PICTURE_LAST 8      /* 8 the cover of what played last, */
#define PICTURE_POSTER 9    /* 9 and 10 the posters of the downloads on House */

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
    char last_heading[16];   /* "Last played", "Now playing", or "" */
    char last_title[96];
    char last_subtitle[96];  /* artist and album */
    bool has_last_cover;
} desk_music_t;

/* The House panel's Code screen: 16 weeks of contributions, Monday first, and per week. */
#define DESK_CODE_DAYS 112
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[24];          /* "CODE · 16 WEEKS" */
    char right[32];          /* "963 CONTRIBUTIONS" */
    int day_count;           /* today is the last */
    uint8_t levels[DESK_CODE_DAYS]; /* 0 to 4, as GitHub's quartiles */
    int month_count;
    struct {
        uint8_t week;
        char name[4];        /* "Jul" */
    } months[6];
    int week_count;
    int16_t weeks[16];       /* each week's total, 0 to 1000 of the busiest */
    char this_week[24];      /* "this week 133" */
    char streak[24];         /* "9-day streak", or "" */
    char busiest[32];        /* "busiest on Tuesdays" */
} desk_code_t;

/* The House panel's My sites screen: a tile per site, ready to draw (app/desk_sites.py). */
#define DESK_SITES 8
#define DESK_SITE_DAYS 30
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[24];          /* "MY SITES · 30 DAYS" */
    char status[16];         /* "ALL UP", "1 DOWN" */
    int down;
    int count;
    struct {
        char name[24];       /* as Kuma has it */
        char state;          /* 'u' up, 'd' down, '?' no heartbeat yet */
        char worst;          /* this month's worst day: 'u', 'b' blip, 'd' outage */
        char left[20];       /* "62 ms", "down 4 min" */
        char right[12];      /* "99.81%", or "" at 100% */
        char days[DESK_SITE_DAYS + 1]; /* oldest first: 'u', 'b', 'd', 'n' no record */
    } sites[DESK_SITES];
} desk_sites_t;

/* The House panel's Tailnet screen: the NAS in the middle, every device round it by
 * how it connects, and the online ones listed. Ready to draw (app/desk_tailnet.py). */
#define DESK_TAILNET_NODES 8
#define DESK_TAILNET_ROWS 5
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[40];          /* "TAILNET · TAIL1234" */
    char status[24];         /* "4 OF 6 ONLINE", "1 HEALTH ISSUE" */
    bool warn;               /* tailscaled has a health warning */
    int node_count;
    struct {
        char label[8];       /* on the tile: "Mac", "iP", "TV" */
        char name[32];
        char kind;           /* 'd' direct, 'r' relay, 'i' idle, 'o' offline */
        bool exit;           /* offers itself as exit node */
        char seen[20];       /* offline: "5 h ago" */
        int x, y;            /* in percent of the map */
    } nodes[DESK_TAILNET_NODES];
    int row_count;
    struct {
        char name[32];
        char ip[20];
        char via[48];        /* "direct", "relay ams", "this NAS", or the health warning */
        char kind;           /* 's' the NAS, else as the nodes */
    } rows[DESK_TAILNET_ROWS];
} desk_tailnet_t;

/* The House panel's NAS screen: the fullest pool as a gauge, CPU and memory with the
 * day as sparklines, the disks and the UPS. Ready to draw (app/desk_nas.py). */
#define DESK_NAS_POINTS 24
#define DESK_NAS_DISKS 8
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[24];          /* "NAS · STORAGE" */
    char status[16];         /* "HEALTHY", "1 ISSUE" */
    bool warn;
    int used_pct, limit_pct; /* the fullest pool, and where it would alert */
    char size[64];           /* "volume2 · 4.9 TB of 6.0 TB" */
    char runway[40];         /* "full in about 5 months", or "" */
    int cpu, ram;            /* % now */
    int cpu_count, ram_count;
    uint8_t cpu_points[DESK_NAS_POINTS], ram_points[DESK_NAS_POINTS]; /* % over the day */
    int disk_count;
    bool disks[DESK_NAS_DISKS]; /* SMART ok */
    char disks_line[16];     /* "5 of 5" */
    char ups[24];            /* "UPS ok", "UPS on battery", or "" */
    bool ups_ok;
} desk_nas_t;

/* The House panel's Backups screen: last run under a seal, the restore check, the NAS to
 * Hetzner line and the nights as bars. Ready to draw (app/desk_backups.py). */
#define DESK_NIGHTS 30
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "BACKUPS" */
    char status[20];         /* "ALL SAFE", "1 PROBLEM" */
    bool warn;               /* an open backup alert */
    bool ok;                 /* the last run went well */
    char time[8];            /* "03:00": when the last run started */
    char line[64];           /* "Last night · 1 h 12 min · 4.1 GB" */
    char restore[64];        /* "Restore verified 12 days ago" */
    char restore_tone;       /* 'o' ok, 'f' failed, 'n' none yet */
    char box[40];            /* "Storage Box · 22% used" */
    int night_count;
    struct {
        uint16_t seconds;    /* how long it took */
        char state;          /* 'o' ok, 's' slow, 'f' failed */
    } nights[DESK_NIGHTS];   /* oldest first */
} desk_backups_t;

/* The House panel's Media screen: the downloads with their posters, the missing episodes
 * and the next to air, or the week ahead when all is in. Ready to draw (app/desk_media.py). */
#define DESK_MEDIA_DOWNLOADS 2
#define DESK_MEDIA_ROWS 3
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "MEDIA" */
    char status[24];         /* "2 DOWNLOADING", "1 NEEDS A LOOK", "UP TO DATE" */
    char tone;               /* 'b' busy, 'w' needs a look or missing, 'o' up to date */
    int download_count;
    struct {
        char title[64];
        char detail[48];     /* "S2 E5 · 1.4 GB" */
        int progress;        /* 0..1000 */
        char pct[8];         /* "72%" */
        char left[24];       /* "6 min", "Importing", "Needs a look" */
        bool trouble;        /* warning or failed */
        bool has_poster;
    } downloads[DESK_MEDIA_DOWNLOADS];
    char missing_title[32];  /* "MISSING · 2 EPISODES", or "" */
    int missing_count;
    int week_count;          /* rows below: missing episodes, or the week ahead */
    struct {
        char title[64];
        char episode[12];    /* "S3 E2" */
        char line[32];       /* "aired 2 days ago", "tomorrow" */
    } rows[DESK_MEDIA_ROWS];
    char next[96];           /* "Next to air: ...", or "" */
} desk_media_t;

/* The House panel's Money screen: the portfolio's gain over a week, a month, a year or all
 * of it, in percentages only (no amounts reach the panel); the points are 0..1000. Ready to
 * draw (app/desk_money.py). */
#define DESK_MONEY_PERIODS 4
#define DESK_MONEY_POINTS 60
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "PORTFOLIO" */
    char today[24];          /* "TODAY +0.1%", or "" */
    bool today_up;
    int period_count;
    struct {
        char key[4];         /* "1W", "1M", "1Y", "All" */
        char label[16];      /* "this week" */
        char change[12];     /* "+4.2%" */
        bool up;
        char high[12];       /* the best point's gain: "+5.3%" */
        int high_at;         /* its index in points */
        char from[16];       /* "16 Oct" */
        char to[12];         /* "Today" */
        int count;
        uint16_t points[DESK_MONEY_POINTS]; /* the gain line, 0..1000 */
    } periods[DESK_MONEY_PERIODS];
} desk_money_t;

/* An open error that takes over every panel until it is dismissed on one of them
 * (the answer's "takeover", app/desk_alerts.py). */
typedef struct {
    bool present;
    uint32_t version;
    char key[96];            /* the incident, for dismissing it */
    char title[128];
    char body[208];
    char since[24];          /* "03:41", "Wed 03:41", "9 Oct" */
} desk_takeover_t;

/* The House panel's Alerts screen: the worst open alert large and the others below, or
 * All quiet with this week's days. Ready to draw (app/desk_alerts.py). */
#define DESK_ALERT_OTHERS 3
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "ALERTS" */
    char status[16];         /* "NONE OPEN", "2 OPEN" */
    char tone;               /* 'k' none open, 'w' worst is a warning, 'e' an error */
    bool has_hero;
    struct {
        char severity[12];   /* "ERROR", "WARNING" */
        char title[128];
        char body[208];      /* the first lines as one */
        char line[48];       /* "Open 16 hours · since 03:41" */
    } hero;
    int other_count;
    struct {
        char severity;       /* 'w' or 'e' */
        char title[128];
    } others[DESK_ALERT_OTHERS];
    char quiet_line[64];     /* "Nothing has needed you for 2 days" */
    struct {
        char letter;         /* 'M' ... 'S' */
        char alert;          /* 0 none, 'w', 'e': the worst opened that day */
        bool today, future;
    } days[7];
} desk_alerts_t;

/* The House panel's Services screen: the outside services in a ring, or the worst
 * incident as a card. Ready to draw (app/desk_services.py). */
#define DESK_SERVICES 8
#define DESK_SERVICE_STEPS 3
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[16];          /* "SERVICES" */
    char status[24];         /* "ALL OPERATIONAL", "1 INCIDENT", "MAINTENANCE" */
    char tone;               /* 'k' ok, 'd' degraded, 'o' outage, 'm' maintenance */
    int count;
    struct {
        char key[16];        /* "github": its logo */
        char name[24];
        char state;          /* 'k', 'd', 'o', 'm', 'u' unknown */
    } services[DESK_SERVICES];
    bool has_incident;
    struct {
        char key[16];
        char name[24];
        char state;
        char line[40];       /* "Degraded · for 24 min" */
        char title[128];     /* the status page's own words */
        int step_count;
        struct {
            char status[24]; /* "Identified" */
            char time[8];    /* "14:15" */
        } steps[DESK_SERVICE_STEPS];
    } incident;
    char others[48];         /* "the other 6 are operational" */
} desk_services_t;

/* The House panel's Top movers screen: the heat map's tiles laid out by the hub
 * (app/desk_movers.py), and the indices below. */
#define DESK_MOVER_TILES 12
#define DESK_INDICES 3
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char title[24];          /* "TOP MOVERS · TODAY" */
    char total[32];          /* "portfolio −0.14%" */
    bool total_up;
    int count;
    struct {
        int16_t x, y, w, h;  /* on the screen */
        char size;           /* 'l' ticker, change and name; 'm' ticker and change; 's' ticker */
        char ticker[16];     /* "NVDA", "3 others" */
        char name[48];
        char change[12];     /* "+2.54%" */
        int16_t move;        /* in hundredths of a percent, for the tint */
    } tiles[DESK_MOVER_TILES];
    int index_count;
    struct {
        char label[16];      /* "S&P 500" */
        char change[12];
        bool up;
    } indices[DESK_INDICES];
} desk_movers_t;

/* The House panel's pipelines (plan.md M21): the running ones as job graphs, at most
 * two (they take turns), and the idle card. Ready to draw (app/desk_pipelines.py). */
#define DESK_PIPELINE_RUNS 2
#define DESK_PIPELINE_JOBS 16
#define DESK_PIPELINE_EDGES 28
typedef struct {
    char title[40];          /* "HOME_KIOSK · MAIN" */
    char number[16];         /* "RUN #312" */
    char position[8];        /* "1 of 2", or "" */
    char state[10];          /* running, approval, success, failure, cancelled */
    uint32_t colour;
    char big[12];            /* "4:12" */
    int64_t since;           /* while it runs: count the big time on from here (epoch s) */
    char first[32];          /* "about 3 min left", "Shipped" */
    char second[40];         /* "usually 6 to 7 min", the failed job */
    char commit[96];
    char meta[48];           /* "Pim · 2a5b2c1" */
    int columns;
    int job_count;
    struct {
        char name[40];
        uint8_t column, row, count;
        char state[10];      /* done, running, queued, approval, failed, cancelled */
        char time[10];       /* "2:05" */
        int16_t progress;    /* 0 to 1000 while running */
    } jobs[DESK_PIPELINE_JOBS];
    int edge_count;
    uint8_t edges[DESK_PIPELINE_EDGES][2]; /* job index from, to */
} desk_run_t;

typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    int count;
    desk_run_t runs[DESK_PIPELINE_RUNS];
} desk_pipeline_t;

typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    int count;
    struct {
        char name[32];
        char line[48];       /* "main · passed 12 min ago" */
        uint32_t colour;
        int bar_count;
        struct {
            int16_t height;  /* 0 to 1000 */
            bool ok;
        } bars[10];
    } repos[3];
} desk_pipelines_t;

/* The Home panel's air: the living room's ALPSTUGA (plan.md M17), ready to draw. */
#define DESK_AIR_HISTORY 97 /* CO2 every 5 minutes over 8 hours */
typedef struct {
    bool present;
    bool stale;
    uint32_t version;
    char room[24];           /* "Living room" */
    char outside[24];        /* "Outside 10°", or "" */
    char temperature[12];    /* "22,9°" */
    char humidity[8];        /* "47%" */
    char pm25[8];            /* "2" */
    char quality[24];        /* the sensor's own verdict: "Good" */
    bool has_co2;
    int co2;                 /* ppm */
    int ring;                /* how far the ring is filled, 0 to 1000 */
    char word[20];           /* "Fresh", "Getting stuffy", "Open a window" */
    uint32_t colour;         /* the word's and the ring's */
    int history_count;
    int16_t history[DESK_AIR_HISTORY];
} desk_air_t;

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
            bool router;     /* a Thread border router */
            bool thread_ok;  /* Thread is up on it */
            bool plays;      /* sends out ripples */
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
void desk_agenda_copy(desk_agenda_t *into);

/* Whether the hub's answer has each screen, without copying its values: the
 * rotation asks every second, and some states are kilobytes (too much to copy
 * onto a task's stack). */
bool desk_has_day(void);
bool desk_has_train(void);
bool desk_has_agenda(void);
bool desk_has_headlines(void);
bool desk_dim(void); /* every living room light is off: the panel dims */
bool desk_rotates(void); /* the panel turns through its screens (the hub's "rotate") */
bool desk_has_lights(void);
uint32_t desk_lights_version(void);
desk_lights_t desk_lights(void);
bool desk_has_playing(void);
uint32_t desk_playing_version(void);
desk_playing_t desk_playing(void);
bool desk_has_music(void);
/* The pipelines are copied into the caller's buffer (in PSRAM), not returned: at
 * about 3 kB they must not land on a task's stack. */
bool desk_has_code(void);
uint32_t desk_code_version(void);
desk_code_t desk_code(void);
bool desk_has_sites(void);
uint32_t desk_sites_version(void);
void desk_sites_copy(desk_sites_t *into);
bool desk_has_services(void);
uint32_t desk_services_version(void);
void desk_services_copy(desk_services_t *into);
bool desk_has_tailnet(void);
uint32_t desk_tailnet_version(void);
void desk_tailnet_copy(desk_tailnet_t *into);
bool desk_has_alerts(void);
uint32_t desk_alerts_version(void);
void desk_alerts_copy(desk_alerts_t *into);
bool desk_has_takeover(void);
uint32_t desk_takeover_version(void);
void desk_takeover_copy(desk_takeover_t *into);
bool desk_has_nas(void);
uint32_t desk_nas_version(void);
void desk_nas_copy(desk_nas_t *into);
bool desk_has_backups(void);
uint32_t desk_backups_version(void);
void desk_backups_copy(desk_backups_t *into);
bool desk_has_media(void);
uint32_t desk_media_version(void);
void desk_media_copy(desk_media_t *into);
bool desk_has_money(void);
uint32_t desk_money_version(void);
void desk_money_copy(desk_money_t *into);
bool desk_has_movers(void);
uint32_t desk_movers_version(void);
void desk_movers_copy(desk_movers_t *into);
bool desk_has_pipeline(void);
uint32_t desk_pipeline_version(void);
void desk_pipeline_copy(desk_pipeline_t *into);
bool desk_has_pipelines(void);
uint32_t desk_pipelines_version(void);
void desk_pipelines_copy(desk_pipelines_t *into);
bool desk_has_air(void);
uint32_t desk_air_version(void);
desk_air_t desk_air(void);
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
