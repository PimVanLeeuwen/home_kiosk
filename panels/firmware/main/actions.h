#pragma once

#include <stdbool.h>

/* The panels' writes to the hub (plan.md M16), sent from their own task so a
 * tap never waits on the network: saving a headline to Readeck, and the living
 * room's lights. */

typedef enum { ACTION_NONE, ACTION_BUSY, ACTION_DONE, ACTION_FAILED } action_result_t;

void actions_start(void);

/* Queue saving the story with this article id; false when the queue is full. */
bool actions_save(const char *article_id);

/* How saving this story went: ACTION_NONE when it was never asked. */
action_result_t actions_saved(const char *article_id);

/* Change a group of lights ("kitchen") or, with group "room", all of them:
 * `body` is the JSON the hub takes, such as {"on":false}. The hub's answer, the
 * new lights screen, is shown at once. */
bool actions_lights(const char *group, const char *body);

/* Spotify from the Home panel: "play", "pause", "next", "previous", or
 * "favourite/2" to start a favourite. The panel asks the hub again soon after. */
bool actions_music(const char *what);

/* Dismiss an error's takeover on every panel (the incident's key); the panel asks
 * the hub again at once. */
bool actions_dismiss(const char *key);
