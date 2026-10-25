/* The Now panel's Briefing screen (plan.md M26) from the hub's answer: the morning
 * digest's title, its line, four facts and when Claude wrote it. Kept apart from
 * desk.c, which is long enough. */

#include "desk_briefing.h"

#include <stdio.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_briefing(const cJSON *screen, desk_briefing_t *briefing)
{
    briefing->present = cJSON_IsTrue(FIELD("present"));
    briefing->stale = cJSON_IsTrue(FIELD("stale"));
    if (!briefing->present) {
        return;
    }
    text(briefing->title, sizeof briefing->title, FIELD("title"));
    text(briefing->line, sizeof briefing->line, FIELD("line"));
    text(briefing->as_of, sizeof briefing->as_of, FIELD("as_of"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("facts"))
    {
        if (briefing->fact_count < 4 && cJSON_IsString(item)) {
            text(briefing->facts[briefing->fact_count++], sizeof briefing->facts[0], item);
        }
    }
}
