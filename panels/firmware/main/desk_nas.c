/* The House panel's NAS screen from the hub's answer: the gauge's numbers, the day's
 * CPU and memory, the disks and the UPS. Kept apart from desk.c, which is long enough. */

#include "desk_nas.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static int number(const cJSON *from)
{
    return cJSON_IsNumber(from) ? from->valueint : 0;
}

/* A sparkline's points, clamped to 0..100. */
static int points(const cJSON *from, uint8_t *into, int room)
{
    int count = 0;
    const cJSON *item;
    cJSON_ArrayForEach(item, from)
    {
        if (count >= room) {
            break;
        }
        int value = number(item);
        into[count++] = (uint8_t)(value < 0 ? 0 : value > 100 ? 100 : value);
    }
    return count;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_nas(const cJSON *screen, desk_nas_t *nas)
{
    nas->present = cJSON_IsTrue(FIELD("present"));
    nas->stale = cJSON_IsTrue(FIELD("stale"));
    if (!nas->present) {
        return;
    }
    text(nas->title, sizeof nas->title, FIELD("title"));
    text(nas->status, sizeof nas->status, FIELD("status"));
    nas->warn = cJSON_IsTrue(FIELD("warn"));
    nas->used_pct = number(FIELD("used_pct"));
    nas->limit_pct = number(FIELD("limit_pct"));
    text(nas->size, sizeof nas->size, FIELD("size"));
    text(nas->runway, sizeof nas->runway, FIELD("runway"));
    nas->cpu = number(FIELD("cpu"));
    nas->ram = number(FIELD("ram"));
    nas->cpu_count = points(FIELD("cpu_points"), nas->cpu_points, DESK_NAS_POINTS);
    nas->ram_count = points(FIELD("ram_points"), nas->ram_points, DESK_NAS_POINTS);
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("disks"))
    {
        if (nas->disk_count >= DESK_NAS_DISKS) {
            break;
        }
        nas->disks[nas->disk_count++] = cJSON_IsTrue(item);
    }
    text(nas->disks_line, sizeof nas->disks_line, FIELD("disks_line"));
    text(nas->ups, sizeof nas->ups, FIELD("ups"));
    nas->ups_ok = !cJSON_IsFalse(FIELD("ups_ok"));
}
