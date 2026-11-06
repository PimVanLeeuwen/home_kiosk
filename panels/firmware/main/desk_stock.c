/* The House panel's Stock screen from the hub's answer: every holding's week, the line
 * and its labels as the hub worded them. Kept apart from desk.c, which is long enough. */

#include "desk_stock.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

/* A point on the 0..1000 scale. */
static uint16_t scaled(const cJSON *from)
{
    int v = cJSON_IsNumber(from) ? from->valueint : 0;
    return (uint16_t)(v < 0 ? 0 : v > 1000 ? 1000 : v);
}

/* An index into the points, or -1 when it is not one. */
static int16_t index_of(const cJSON *from, int count)
{
    int v = cJSON_IsNumber(from) ? from->valueint : -1;
    return (int16_t)(v >= 0 && v < count ? v : -1);
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)
#define ITEM(name) cJSON_GetObjectItem(item, name)

void desk_parse_stock(const cJSON *screen, desk_stock_t *stock)
{
    stock->present = cJSON_IsTrue(FIELD("present"));
    stock->stale = cJSON_IsTrue(FIELD("stale"));
    if (!stock->present) {
        return;
    }
    text(stock->title, sizeof stock->title, FIELD("title"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("stocks"))
    {
        if (stock->count >= DESK_STOCKS) {
            break;
        }
        typeof(stock->stocks[0]) *s = &stock->stocks[stock->count];
        const cJSON *point;
        cJSON_ArrayForEach(point, ITEM("points"))
        {
            if (s->count >= DESK_STOCK_POINTS) {
                break;
            }
            s->points[s->count++] = scaled(point);
        }
        if (s->count < 2) {
            memset(s, 0, sizeof *s);
            continue; /* no line to draw */
        }
        stock->count++;
        text(s->ticker, sizeof s->ticker, ITEM("ticker"));
        text(s->name, sizeof s->name, ITEM("name"));
        text(s->price, sizeof s->price, ITEM("price"));
        text(s->week, sizeof s->week, ITEM("week"));
        s->up = !cJSON_IsFalse(ITEM("up"));
        text(s->today, sizeof s->today, ITEM("today"));
        s->today_up = !cJSON_IsFalse(ITEM("today_up"));
        text(s->gain, sizeof s->gain, ITEM("gain"));
        s->gain_up = !cJSON_IsFalse(ITEM("gain_up"));
        text(s->high, sizeof s->high, ITEM("high"));
        text(s->low, sizeof s->low, ITEM("low"));
        s->high_at = index_of(ITEM("high_at"), s->count);
        s->low_at = index_of(ITEM("low_at"), s->count);
        s->base = scaled(ITEM("base"));
        const cJSON *day;
        cJSON_ArrayForEach(day, ITEM("days"))
        {
            int16_t at = index_of(cJSON_GetObjectItem(day, "at"), s->count);
            if (s->day_count >= DESK_STOCK_DAYS || at < 0) {
                continue;
            }
            s->days[s->day_count].at = at;
            text(s->days[s->day_count].label, sizeof s->days[0].label, cJSON_GetObjectItem(day, "label"));
            s->day_count++;
        }
    }
    if (stock->count == 0) {
        stock->present = false;
    }
}
