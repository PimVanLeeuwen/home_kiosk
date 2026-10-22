/* The House panel's Services screen from the hub's answer: the services for the ring
 * and, during an incident, the worst one's card. Kept apart from desk.c, which is long
 * enough. */

#include "desk_services.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

/* "ok", "degraded", "outage", "maintenance", "unknown" as one letter. */
static char state(const cJSON *from)
{
    const char *word = cJSON_IsString(from) ? from->valuestring : "";
    return strcmp(word, "ok") == 0 ? 'k' : word[0] == 'd' ? 'd' : word[0] == 'o' ? 'o' : word[0] == 'm' ? 'm' : 'u';
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)
#define ITEM(name) cJSON_GetObjectItem(item, name)

void desk_parse_services(const cJSON *screen, desk_services_t *services)
{
    services->present = cJSON_IsTrue(FIELD("present"));
    services->stale = cJSON_IsTrue(FIELD("stale"));
    if (!services->present) {
        return;
    }
    text(services->title, sizeof services->title, FIELD("title"));
    text(services->status, sizeof services->status, FIELD("status"));
    text(services->others, sizeof services->others, FIELD("others"));
    services->tone = state(FIELD("tone"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("services"))
    {
        if (services->count >= DESK_SERVICES) {
            break;
        }
        typeof(services->services[0]) *service = &services->services[services->count++];
        text(service->key, sizeof service->key, ITEM("key"));
        text(service->name, sizeof service->name, ITEM("name"));
        service->state = state(ITEM("state"));
    }
    item = FIELD("incident");
    services->has_incident = cJSON_IsObject(item);
    if (!services->has_incident) {
        return;
    }
    typeof(services->incident) *incident = &services->incident;
    text(incident->key, sizeof incident->key, ITEM("key"));
    text(incident->name, sizeof incident->name, ITEM("name"));
    text(incident->line, sizeof incident->line, ITEM("line"));
    text(incident->title, sizeof incident->title, ITEM("title"));
    incident->state = state(ITEM("state"));
    const cJSON *step;
    cJSON_ArrayForEach(step, ITEM("steps"))
    {
        if (incident->step_count >= DESK_SERVICE_STEPS) {
            break;
        }
        text(incident->steps[incident->step_count].status, sizeof incident->steps[0].status,
             cJSON_GetObjectItem(step, "status"));
        text(incident->steps[incident->step_count++].time, sizeof incident->steps[0].time,
             cJSON_GetObjectItem(step, "time"));
    }
}
