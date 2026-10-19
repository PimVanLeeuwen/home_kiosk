/* The panels' writes to the hub: POST /api/desk/save with the board's device
 * key (app/desk_keys.py). A tap fills the bookmark at once; the outcome is kept
 * per story, so the screen can empty it again when saving failed. */

#include "actions.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "net.h"
#include "sdkconfig.h"

static const char *TAG = "actions";

#define REMEMBERED 6

static QueueHandle_t queue;
static SemaphoreHandle_t lock;
static struct {
    char id[20];
    action_result_t result;
} outcomes[REMEMBERED];
static int next_outcome;

static void note(const char *id, action_result_t result)
{
    xSemaphoreTake(lock, portMAX_DELAY);
    int slot = -1;
    for (int i = 0; i < REMEMBERED; i++) {
        if (strcmp(outcomes[i].id, id) == 0) {
            slot = i;
        }
    }
    if (slot < 0) {
        slot = next_outcome;
        next_outcome = (next_outcome + 1) % REMEMBERED;
        snprintf(outcomes[slot].id, sizeof outcomes[slot].id, "%s", id);
    }
    outcomes[slot].result = result;
    xSemaphoreGive(lock);
}

action_result_t actions_saved(const char *article_id)
{
    action_result_t result = ACTION_NONE;
    if (lock == NULL) {
        return result;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    for (int i = 0; i < REMEMBERED; i++) {
        if (strcmp(outcomes[i].id, article_id) == 0) {
            result = outcomes[i].result;
        }
    }
    xSemaphoreGive(lock);
    return result;
}

bool actions_save(const char *article_id)
{
    char id[20];
    snprintf(id, sizeof id, "%s", article_id);
    if (queue == NULL || xQueueSend(queue, id, 0) != pdTRUE) {
        return false;
    }
    note(id, ACTION_BUSY);
    return true;
}

static int post_save(const char *id)
{
    char key[64], auth[80], url[160], body[64];
    desk_key(key, sizeof key);
    if (key[0] == '\0') {
        return -1; /* no key yet: the board needs a panel in Settings */
    }
    snprintf(auth, sizeof auth, "Bearer %s", key);
    snprintf(url, sizeof url, "%s/api/desk/save", CONFIG_PANEL_HUB_URL);
    int length = snprintf(body, sizeof body, "{\"article_id\":\"%s\"}", id);
    esp_http_client_config_t config = {.url = url, .method = HTTP_METHOD_POST, .timeout_ms = 15000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Authorization", auth);
    esp_http_client_set_post_field(client, body, length);
    int status = esp_http_client_perform(client) == ESP_OK ? esp_http_client_get_status_code(client) : 0;
    esp_http_client_cleanup(client);
    return status;
}

static void actions_task(void *arg)
{
    char id[20];
    for (;;) {
        xQueueReceive(queue, id, portMAX_DELAY);
        int status = net_state().connected ? post_save(id) : 0;
        note(id, status == 200 ? ACTION_DONE : ACTION_FAILED);
        if (status != 200) {
            ESP_LOGW(TAG, "saving a story failed (%d)", status);
        } else {
            ESP_LOGI(TAG, "story saved");
        }
    }
}

void actions_start(void)
{
    lock = xSemaphoreCreateMutex();
    queue = xQueueCreate(4, sizeof(char[20]));
    xTaskCreate(actions_task, "actions", 6144, NULL, 3, NULL);
}
