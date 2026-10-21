/* The House panel's Code screen (plan.md M20) from the hub's answer: the levels of
 * 16 weeks of contributions, Monday first, the months over the grid, each week's
 * total and the three lines below. Kept apart from desk.c, which is long enough. */

#include "desk_code.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_code(const cJSON *screen, desk_code_t *code)
{
    code->present = cJSON_IsTrue(FIELD("present"));
    code->stale = cJSON_IsTrue(FIELD("stale"));
    if (!code->present) {
        return;
    }
    text(code->title, sizeof code->title, FIELD("title"));
    text(code->right, sizeof code->right, FIELD("right"));
    text(code->this_week, sizeof code->this_week, FIELD("this_week"));
    text(code->streak, sizeof code->streak, FIELD("streak"));
    text(code->busiest, sizeof code->busiest, FIELD("busiest"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("levels"))
    {
        if (code->day_count < DESK_CODE_DAYS && cJSON_IsNumber(item)) {
            code->levels[code->day_count++] = (uint8_t)item->valueint;
        }
    }
    cJSON_ArrayForEach(item, FIELD("months"))
    {
        if (code->month_count < 6) {
            const cJSON *week = cJSON_GetObjectItem(item, "week");
            code->months[code->month_count].week = cJSON_IsNumber(week) ? (uint8_t)week->valueint : 0;
            text(code->months[code->month_count++].name, sizeof code->months[0].name,
                 cJSON_GetObjectItem(item, "name"));
        }
    }
    cJSON_ArrayForEach(item, FIELD("weeks"))
    {
        if (code->week_count < 16 && cJSON_IsNumber(item)) {
            code->weeks[code->week_count++] = (int16_t)item->valueint;
        }
    }
}
