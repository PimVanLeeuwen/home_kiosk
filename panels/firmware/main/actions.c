/* The panels' writes to the hub, with the board's device key (app/desk_keys.py):
 * POST /api/desk/save for a headline (a tap fills the bookmark at once; the
 * outcome is kept per story, so the screen can empty it again when saving
 * failed), and POST /api/desk/lights/... for the living room, whose answer is
 * the new lights screen. */

#include "actions.h"

#include <stdio.h>
#include <string.h>

#include "desk.h"
#include "esp_heap_caps.h"
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
#define REPLY_MAX 4096

typedef struct {
    char id[20];    /* a story's article id, for saving it; "" for lights */
    char path[48];  /* "/api/desk/lights/kitchen" */
    char body[64];
} action_t;

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
    action_t action = {0};
    snprintf(action.id, sizeof action.id, "%s", article_id);
    snprintf(action.path, sizeof action.path, "/api/desk/save");
    snprintf(action.body, sizeof action.body, "{\"article_id\":\"%s\"}", article_id);
    if (queue == NULL || xQueueSend(queue, &action, 0) != pdTRUE) {
        return false;
    }
    note(action.id, ACTION_BUSY);
    return true;
}

bool actions_lights(const char *group, const char *body)
{
    action_t action = {0};
    snprintf(action.path, sizeof action.path, "/api/desk/lights/%s", group);
    snprintf(action.body, sizeof action.body, "%s", body);
    return queue != NULL && xQueueSend(queue, &action, 0) == pdTRUE;
}

/* POST `body` to the hub with the board's key; the answer goes into `reply`. */
static int post(const char *path, const char *body, char *reply, size_t room)
{
    char key[64], auth[80], url[160];
    desk_key(key, sizeof key);
    if (key[0] == '\0') {
        return -1; /* no key yet: the board needs a panel in Settings */
    }
    snprintf(auth, sizeof auth, "Bearer %s", key);
    snprintf(url, sizeof url, "%s%s", CONFIG_PANEL_HUB_URL, path);
    esp_http_client_config_t config = {.url = url, .method = HTTP_METHOD_POST, .timeout_ms = 15000};
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_header(client, "Authorization", auth);
    int status = 0;
    size_t length = 0, size = strlen(body);
    if (esp_http_client_open(client, size) == ESP_OK &&
        esp_http_client_write(client, body, size) == (int)size && esp_http_client_fetch_headers(client) >= 0) {
        status = esp_http_client_get_status_code(client);
        int read;
        while (length < room - 1 && (read = esp_http_client_read(client, reply + length, room - 1 - length)) > 0) {
            length += read;
        }
    }
    reply[length] = '\0';
    esp_http_client_cleanup(client);
    return status;
}

bool actions_music(const char *what)
{
    action_t action = {0};
    snprintf(action.path, sizeof action.path, "/api/desk/music/%s", what);
    snprintf(action.body, sizeof action.body, "{}");
    return queue != NULL && xQueueSend(queue, &action, 0) == pdTRUE;
}

static void actions_task(void *arg)
{
    action_t action;
    char *reply = heap_caps_malloc(REPLY_MAX, MALLOC_CAP_SPIRAM);
    for (;;) {
        xQueueReceive(queue, &action, portMAX_DELAY);
        int status = net_state().connected && reply ? post(action.path, action.body, reply, REPLY_MAX) : 0;
        if (action.id[0]) {
            note(action.id, status == 200 ? ACTION_DONE : ACTION_FAILED);
        } else if (status == 200 && strstr(action.path, "/lights/")) {
            desk_take_lights(reply); /* the new state, at once */
        } else if (status == 200) {
            vTaskDelay(pdMS_TO_TICKS(1200)); /* Spotify takes a moment to tell */
            desk_poll_now();
        }
        if (status != 200) {
            ESP_LOGW(TAG, "%s failed (%d)", action.path, status);
            desk_poll_now(); /* show what really is, not what the tap hoped for */
        } else {
            ESP_LOGI(TAG, "%s done", action.path);
        }
    }
}

void actions_start(void)
{
    lock = xSemaphoreCreateMutex();
    queue = xQueueCreate(6, sizeof(action_t));
    xTaskCreate(actions_task, "actions", 6144, NULL, 3, NULL);
}
