/* The House panel's Money screen from the hub's answer: today's change and the periods,
 * each with its gain line. Kept apart from desk.c, which is long enough. */

#include "desk_money.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_money(const cJSON *screen, desk_money_t *money)
{
    money->present = cJSON_IsTrue(FIELD("present"));
    money->stale = cJSON_IsTrue(FIELD("stale"));
    if (!money->present) {
        return;
    }
    text(money->title, sizeof money->title, FIELD("title"));
    text(money->today, sizeof money->today, FIELD("today"));
    money->today_up = !cJSON_IsFalse(FIELD("today_up"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("periods"))
    {
        if (money->period_count >= DESK_MONEY_PERIODS) {
            break;
        }
        typeof(money->periods[0]) *p = &money->periods[money->period_count++];
        text(p->key, sizeof p->key, cJSON_GetObjectItem(item, "key"));
        text(p->label, sizeof p->label, cJSON_GetObjectItem(item, "label"));
        text(p->change, sizeof p->change, cJSON_GetObjectItem(item, "change"));
        p->up = !cJSON_IsFalse(cJSON_GetObjectItem(item, "up"));
        text(p->high, sizeof p->high, cJSON_GetObjectItem(item, "high"));
        const cJSON *at = cJSON_GetObjectItem(item, "high_at");
        p->high_at = cJSON_IsNumber(at) ? at->valueint : -1;
        text(p->from, sizeof p->from, cJSON_GetObjectItem(item, "from"));
        text(p->to, sizeof p->to, cJSON_GetObjectItem(item, "to"));
        const cJSON *point;
        cJSON_ArrayForEach(point, cJSON_GetObjectItem(item, "points"))
        {
            if (p->count >= DESK_MONEY_POINTS) {
                break;
            }
            int v = cJSON_IsNumber(point) ? point->valueint : 0;
            p->points[p->count++] = (uint16_t)(v < 0 ? 0 : v > 1000 ? 1000 : v);
        }
        if (p->high_at >= p->count) {
            p->high_at = -1;
        }
    }
}
