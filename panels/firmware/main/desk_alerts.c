/* The House panel's Alerts screen from the hub's answer: the worst open alert and the
 * others, or the quiet week. Kept apart from desk.c, which is long enough. */

#include "desk_alerts.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

/* "error", "warning", "ok": 'e', 'w', or 0 for anything else. */
static char tone(const cJSON *from)
{
    if (!cJSON_IsString(from)) {
        return 0;
    }
    return from->valuestring[0] == 'e' ? 'e' : from->valuestring[0] == 'w' ? 'w' : 0;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_alerts(const cJSON *screen, desk_alerts_t *alerts)
{
    alerts->present = cJSON_IsTrue(FIELD("present"));
    alerts->stale = cJSON_IsTrue(FIELD("stale"));
    if (!alerts->present) {
        return;
    }
    text(alerts->title, sizeof alerts->title, FIELD("title"));
    text(alerts->status, sizeof alerts->status, FIELD("status"));
    char worst = tone(FIELD("tone"));
    alerts->tone = worst ? worst : 'k';

    const cJSON *hero = FIELD("hero");
    alerts->has_hero = cJSON_IsObject(hero);
    if (alerts->has_hero) {
        text(alerts->hero.severity, sizeof alerts->hero.severity, cJSON_GetObjectItem(hero, "severity"));
        text(alerts->hero.title, sizeof alerts->hero.title, cJSON_GetObjectItem(hero, "title"));
        text(alerts->hero.body, sizeof alerts->hero.body, cJSON_GetObjectItem(hero, "body"));
        text(alerts->hero.line, sizeof alerts->hero.line, cJSON_GetObjectItem(hero, "line"));
    }
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("others"))
    {
        if (alerts->other_count >= DESK_ALERT_OTHERS) {
            break;
        }
        typeof(alerts->others[0]) *other = &alerts->others[alerts->other_count++];
        other->severity = tone(cJSON_GetObjectItem(item, "severity"));
        text(other->title, sizeof other->title, cJSON_GetObjectItem(item, "title"));
    }

    const cJSON *quiet = FIELD("quiet");
    text(alerts->quiet_line, sizeof alerts->quiet_line, cJSON_GetObjectItem(quiet, "line"));
    int d = 0;
    cJSON_ArrayForEach(item, cJSON_GetObjectItem(quiet, "days"))
    {
        if (d >= 7) {
            break;
        }
        const cJSON *letter = cJSON_GetObjectItem(item, "letter");
        alerts->days[d].letter = cJSON_IsString(letter) && letter->valuestring[0] ? letter->valuestring[0] : ' ';
        alerts->days[d].alert = tone(cJSON_GetObjectItem(item, "alert"));
        alerts->days[d].today = cJSON_IsTrue(cJSON_GetObjectItem(item, "today"));
        alerts->days[d].future = cJSON_IsTrue(cJSON_GetObjectItem(item, "future"));
        d++;
    }
}
