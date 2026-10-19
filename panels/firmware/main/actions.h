#pragma once

#include <stdbool.h>

/* The panels' writes to the hub (plan.md M16), sent from their own task so a
 * tap never waits on the network: for now saving a headline to Readeck. */

typedef enum { ACTION_NONE, ACTION_BUSY, ACTION_DONE, ACTION_FAILED } action_result_t;

void actions_start(void);

/* Queue saving the story with this article id; false when the queue is full. */
bool actions_save(const char *article_id);

/* How saving this story went: ACTION_NONE when it was never asked. */
action_result_t actions_saved(const char *article_id);
