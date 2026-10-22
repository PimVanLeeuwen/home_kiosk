/* The House panel's Top movers screen from the hub's answer: the tiles as the hub laid
 * them out, and the indices. Kept apart from desk.c, which is long enough. */

#include "desk_movers.h"

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

#define FIELD(name) cJSON_GetObjectItem(screen, name)
#define ITEM(name) cJSON_GetObjectItem(item, name)

void desk_parse_movers(const cJSON *screen, desk_movers_t *movers)
{
    movers->present = cJSON_IsTrue(FIELD("present"));
    movers->stale = cJSON_IsTrue(FIELD("stale"));
    if (!movers->present) {
        return;
    }
    text(movers->title, sizeof movers->title, FIELD("title"));
    text(movers->total, sizeof movers->total, FIELD("total"));
    movers->total_up = !cJSON_IsFalse(FIELD("total_up"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("tiles"))
    {
        if (movers->count >= DESK_MOVER_TILES) {
            break;
        }
        typeof(movers->tiles[0]) *tile = &movers->tiles[movers->count++];
        tile->x = (int16_t)number(ITEM("x"));
        tile->y = (int16_t)number(ITEM("y"));
        tile->w = (int16_t)number(ITEM("w"));
        tile->h = (int16_t)number(ITEM("h"));
        tile->move = (int16_t)number(ITEM("move"));
        const cJSON *size = ITEM("size");
        tile->size = cJSON_IsString(size) && size->valuestring[0] ? size->valuestring[0] : 's';
        text(tile->ticker, sizeof tile->ticker, ITEM("ticker"));
        text(tile->name, sizeof tile->name, ITEM("name"));
        text(tile->change, sizeof tile->change, ITEM("change"));
    }
    cJSON_ArrayForEach(item, FIELD("indices"))
    {
        if (movers->index_count >= DESK_INDICES) {
            break;
        }
        typeof(movers->indices[0]) *index = &movers->indices[movers->index_count++];
        text(index->label, sizeof index->label, ITEM("label"));
        text(index->change, sizeof index->change, ITEM("change"));
        index->up = cJSON_IsTrue(ITEM("up"));
    }
}
