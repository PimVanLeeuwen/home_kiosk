/* The Now panel's Todos screen (plan.md M37) from the hub's answer: the title, the open
 * todos with their due word, state and High, and how many more. Kept apart from desk.c,
 * which is long enough. */

#include "desk_todos.h"

#include <stdio.h>
#include <string.h>

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_todos(const cJSON *screen, desk_todos_t *todos)
{
    todos->present = cJSON_IsTrue(FIELD("present"));
    todos->stale = cJSON_IsTrue(FIELD("stale"));
    if (!todos->present) {
        return;
    }
    text(todos->title, sizeof todos->title, FIELD("title"));
    const cJSON *item;
    cJSON_ArrayForEach(item, FIELD("todos"))
    {
        if (todos->count == DESK_TODOS) {
            break;
        }
        typeof(todos->todos[0]) *t = &todos->todos[todos->count++];
        text(t->title, sizeof t->title, cJSON_GetObjectItem(item, "title"));
        text(t->due, sizeof t->due, cJSON_GetObjectItem(item, "due"));
        const cJSON *state = cJSON_GetObjectItem(item, "state");
        t->state = !cJSON_IsString(state)                         ? 0
                   : strcmp(state->valuestring, "overdue") == 0 ? 'o'
                   : strcmp(state->valuestring, "today") == 0   ? 't'
                                                                 : 0;
        t->high = cJSON_IsTrue(cJSON_GetObjectItem(item, "high"));
    }
    const cJSON *more = FIELD("more");
    todos->more = cJSON_IsNumber(more) ? more->valueint : 0;
}
