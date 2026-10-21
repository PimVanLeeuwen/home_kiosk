/* The House panel's My sites screen from the hub's answer: a tile per site with its
 * words ready to draw and its 30 days as letters. Kept apart from desk.c, which is
 * long enough. */

#include "desk_sites.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static char letter(const cJSON *from, char otherwise)
{
    return cJSON_IsString(from) && from->valuestring[0] ? from->valuestring[0] : otherwise;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_sites(const cJSON *screen, desk_sites_t *sites)
{
    sites->present = cJSON_IsTrue(FIELD("present"));
    sites->stale = cJSON_IsTrue(FIELD("stale"));
    if (!sites->present) {
        return;
    }
    text(sites->title, sizeof sites->title, FIELD("title"));
    text(sites->status, sizeof sites->status, FIELD("status"));
    const cJSON *down = FIELD("down");
    sites->down = cJSON_IsNumber(down) ? down->valueint : 0;
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("sites"))
    {
        if (sites->count >= DESK_SITES) {
            break;
        }
        typeof(sites->sites[0]) *site = &sites->sites[sites->count++];
        text(site->name, sizeof site->name, cJSON_GetObjectItem(item, "name"));
        text(site->left, sizeof site->left, cJSON_GetObjectItem(item, "left"));
        text(site->right, sizeof site->right, cJSON_GetObjectItem(item, "right"));
        text(site->days, sizeof site->days, cJSON_GetObjectItem(item, "days"));
        /* "up", "down", "unknown" and "up", "blip", "down": their first letters. */
        char state = letter(cJSON_GetObjectItem(item, "state"), '?');
        site->state = state == 'u' || state == 'd' ? state : '?';
        site->worst = letter(cJSON_GetObjectItem(item, "worst"), 'u');
    }
}
