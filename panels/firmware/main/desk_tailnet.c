/* The House panel's Tailnet screen from the hub's answer: the devices with their
 * place on the map, and the rows under it. Kept apart from desk.c, which is long
 * enough. */

#include "desk_tailnet.h"

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

/* "direct", "relay", "idle", "offline", "self": their first letters. */
static char kind(const cJSON *from)
{
    char k = cJSON_IsString(from) && from->valuestring[0] ? from->valuestring[0] : 'o';
    return strchr("drios", k) ? k : 'o';
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_tailnet(const cJSON *screen, desk_tailnet_t *tailnet)
{
    tailnet->present = cJSON_IsTrue(FIELD("present"));
    tailnet->stale = cJSON_IsTrue(FIELD("stale"));
    if (!tailnet->present) {
        return;
    }
    text(tailnet->title, sizeof tailnet->title, FIELD("title"));
    text(tailnet->status, sizeof tailnet->status, FIELD("status"));
    tailnet->warn = cJSON_IsTrue(FIELD("warn"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("nodes"))
    {
        if (tailnet->node_count >= DESK_TAILNET_NODES) {
            break;
        }
        typeof(tailnet->nodes[0]) *node = &tailnet->nodes[tailnet->node_count++];
        text(node->label, sizeof node->label, cJSON_GetObjectItem(item, "label"));
        text(node->name, sizeof node->name, cJSON_GetObjectItem(item, "name"));
        text(node->seen, sizeof node->seen, cJSON_GetObjectItem(item, "seen"));
        node->kind = kind(cJSON_GetObjectItem(item, "kind"));
        node->exit = cJSON_IsTrue(cJSON_GetObjectItem(item, "exit"));
        node->x = number(cJSON_GetObjectItem(item, "x"));
        node->y = number(cJSON_GetObjectItem(item, "y"));
    }
    cJSON_ArrayForEach(item, FIELD("rows"))
    {
        if (tailnet->row_count >= DESK_TAILNET_ROWS) {
            break;
        }
        typeof(tailnet->rows[0]) *row = &tailnet->rows[tailnet->row_count++];
        text(row->name, sizeof row->name, cJSON_GetObjectItem(item, "name"));
        text(row->ip, sizeof row->ip, cJSON_GetObjectItem(item, "ip"));
        text(row->via, sizeof row->via, cJSON_GetObjectItem(item, "via"));
        row->kind = kind(cJSON_GetObjectItem(item, "kind"));
    }
}
