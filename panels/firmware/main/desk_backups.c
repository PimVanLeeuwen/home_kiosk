/* The House panel's Backups screen from the hub's answer: the last run, the restore check,
 * the Storage Box and the nights. Kept apart from desk.c, which is long enough. */

#include "desk_backups.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

/* A word's first letter if it is one of `allowed`, else `otherwise`. */
static char letter(const cJSON *from, const char *allowed, char otherwise)
{
    char c = cJSON_IsString(from) && from->valuestring[0] ? from->valuestring[0] : 0;
    return c && strchr(allowed, c) ? c : otherwise;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_backups(const cJSON *screen, desk_backups_t *backups)
{
    backups->present = cJSON_IsTrue(FIELD("present"));
    backups->stale = cJSON_IsTrue(FIELD("stale"));
    if (!backups->present) {
        return;
    }
    text(backups->title, sizeof backups->title, FIELD("title"));
    text(backups->status, sizeof backups->status, FIELD("status"));
    backups->warn = cJSON_IsTrue(FIELD("warn"));
    backups->ok = !cJSON_IsFalse(FIELD("ok"));
    text(backups->time, sizeof backups->time, FIELD("time"));
    text(backups->line, sizeof backups->line, FIELD("line"));
    text(backups->restore, sizeof backups->restore, FIELD("restore"));
    /* "ok", "failed", "none" */
    backups->restore_tone = letter(FIELD("restore_tone"), "ofn", 'n');
    text(backups->box, sizeof backups->box, FIELD("box"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("nights"))
    {
        if (backups->night_count >= DESK_NIGHTS) {
            break;
        }
        const cJSON *minutes = cJSON_GetObjectItem(item, "minutes");
        int m = cJSON_IsNumber(minutes) ? minutes->valueint : 0;
        backups->nights[backups->night_count].minutes = (uint16_t)(m < 0 ? 0 : m > 6000 ? 6000 : m);
        /* "ok", "slow", "failed" */
        backups->nights[backups->night_count].state = letter(cJSON_GetObjectItem(item, "state"), "osf", 'o');
        backups->night_count++;
    }
}
