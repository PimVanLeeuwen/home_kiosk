/* The House panel's Media screen from the hub's answer: the downloads (their posters are
 * asked of pictures.c, slots PICTURE_POSTER on), the missing episodes or the week ahead,
 * and the next to air. Kept apart from desk.c, which is long enough. */

#include "desk_media.h"

#include <stdio.h>
#include <string.h>

#include "pictures.h"

static void text(char *to, size_t size, const cJSON *from)
{
    snprintf(to, size, "%s", cJSON_IsString(from) ? from->valuestring : "");
}

static int rows(const cJSON *from, desk_media_t *media)
{
    int count = 0;
    const cJSON *item;
    cJSON_ArrayForEach(item, from)
    {
        if (count >= DESK_MEDIA_ROWS) {
            break;
        }
        text(media->rows[count].title, sizeof media->rows[count].title, cJSON_GetObjectItem(item, "title"));
        text(media->rows[count].episode, sizeof media->rows[count].episode, cJSON_GetObjectItem(item, "episode"));
        text(media->rows[count].line, sizeof media->rows[count].line, cJSON_GetObjectItem(item, "line"));
        count++;
    }
    return count;
}

#define FIELD(name) cJSON_GetObjectItem(screen, name)

void desk_parse_media(const cJSON *screen, desk_media_t *media)
{
    media->present = cJSON_IsTrue(FIELD("present"));
    media->stale = cJSON_IsTrue(FIELD("stale"));
    if (media->present) {
        text(media->title, sizeof media->title, FIELD("title"));
        text(media->status, sizeof media->status, FIELD("status"));
        const cJSON *tone = FIELD("tone");
        char t = cJSON_IsString(tone) ? tone->valuestring[0] : 'o';
        media->tone = t == 'b' ? 'b' : t == 'w' ? 'w' : 'o'; /* "busy", "warn", "ok" */
        const cJSON *item;
        cJSON_ArrayForEach(item, FIELD("downloads"))
        {
            if (media->download_count >= DESK_MEDIA_DOWNLOADS) {
                break;
            }
            int i = media->download_count++;
            typeof(media->downloads[0]) *d = &media->downloads[i];
            text(d->title, sizeof d->title, cJSON_GetObjectItem(item, "title"));
            text(d->detail, sizeof d->detail, cJSON_GetObjectItem(item, "detail"));
            const cJSON *progress = cJSON_GetObjectItem(item, "progress");
            d->progress = cJSON_IsNumber(progress) ? progress->valueint : 0;
            d->progress = d->progress < 0 ? 0 : d->progress > 1000 ? 1000 : d->progress;
            text(d->pct, sizeof d->pct, cJSON_GetObjectItem(item, "pct"));
            text(d->left, sizeof d->left, cJSON_GetObjectItem(item, "left"));
            const cJSON *state = cJSON_GetObjectItem(item, "state");
            d->trouble = cJSON_IsString(state) &&
                         (strcmp(state->valuestring, "warning") == 0 || strcmp(state->valuestring, "failed") == 0);
            const cJSON *poster = cJSON_GetObjectItem(item, "poster");
            d->has_poster = cJSON_IsString(poster);
            pictures_want(PICTURE_POSTER + i, d->has_poster ? poster->valuestring : "");
        }
        text(media->missing_title, sizeof media->missing_title, FIELD("missing_title"));
        media->missing_count = rows(FIELD("missing"), media);
        if (media->missing_count == 0) {
            media->week_count = rows(FIELD("week"), media);
        }
        text(media->next, sizeof media->next, FIELD("next"));
    }
    for (int i = media->download_count; i < DESK_MEDIA_DOWNLOADS; i++) {
        pictures_want(PICTURE_POSTER + i, "");
    }
}
