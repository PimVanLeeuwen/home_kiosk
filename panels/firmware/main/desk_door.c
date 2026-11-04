/* The Door panel's today view (plan.md M32) from the hub's answer: the weather to go out,
 * today's open reminders and the coming week's birthdays. Kept apart from desk.c, which is
 * long enough. */

#include "desk_door.h"

#include <stdio.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static int64_t seconds(const cJSON *from)
{
    return cJSON_IsNumber(from) ? (int64_t)from->valuedouble : 0;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_door(const cJSON *screen, desk_door_t *door)
{
    door->present = cJSON_IsTrue(FIELD("present"));
    door->stale = cJSON_IsTrue(FIELD("stale"));
    if (!door->present) {
        return;
    }
    text(door->date, sizeof door->date, FIELD("date"));
    const cJSON *temperature = FIELD("temperature");
    door->has_temperature = cJSON_IsNumber(temperature);
    door->temperature = door->has_temperature ? temperature->valueint : 0;
    text(door->description, sizeof door->description, FIELD("description"));
    text(door->tonight, sizeof door->tonight, FIELD("tonight"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("rain"))
    {
        if (door->rain_count < DESK_DOOR_RAIN && cJSON_IsNumber(item)) {
            door->rain[door->rain_count++] = (float)item->valuedouble;
        }
    }
    door->rain_from = seconds(FIELD("rain_from"));
    door->rain_step = (int)seconds(FIELD("rain_step"));
    door->wet = cJSON_IsTrue(FIELD("wet"));
    door->wet_from = seconds(FIELD("wet_from"));
    door->wet_until = seconds(FIELD("wet_until"));
    text(door->wind, sizeof door->wind, FIELD("wind"));
    cJSON_ArrayForEach(item, FIELD("reminders"))
    {
        if (door->reminder_count == DESK_DOOR_REMINDERS) {
            break;
        }
        typeof(door->reminders[0]) *r = &door->reminders[door->reminder_count++];
        text(r->title, sizeof r->title, cJSON_GetObjectItem(item, "title"));
        text(r->at, sizeof r->at, cJSON_GetObjectItem(item, "at"));
    }
    door->more_reminders = (int)seconds(FIELD("more_reminders"));
    cJSON_ArrayForEach(item, FIELD("birthdays"))
    {
        if (door->birthday_count == DESK_DOOR_BIRTHDAYS) {
            break;
        }
        typeof(door->birthdays[0]) *b = &door->birthdays[door->birthday_count++];
        text(b->name, sizeof b->name, cJSON_GetObjectItem(item, "name"));
        text(b->when, sizeof b->when, cJSON_GetObjectItem(item, "when"));
        b->turns = (int)seconds(cJSON_GetObjectItem(item, "turns"));
        b->today = cJSON_IsTrue(cJSON_GetObjectItem(item, "today"));
    }
}
