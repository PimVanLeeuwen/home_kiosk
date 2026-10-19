/* Wi-Fi through the ESP32-C6 with ESP-Hosted (the esp_wifi API is the same).
 * The hub is asked in desk.c, which reports its answers here. */

#include "net.h"

#include <stdio.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "net";
static net_state_t state;
static SemaphoreHandle_t lock;

net_state_t net_state(void)
{
    net_state_t copy;
    if (lock == NULL) {
        return state; /* the screen asks before Wi-Fi has started: nothing yet */
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    copy = state;
    xSemaphoreGive(lock);
    return copy;
}

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xSemaphoreTake(lock, portMAX_DELAY);
        state.connected = false;
        state.rssi = 0;
        state.disconnects++;
        xSemaphoreGive(lock);
        ESP_LOGW(TAG, "disconnected, retrying");
        vTaskDelay(pdMS_TO_TICKS(2000));
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)data;
        xSemaphoreTake(lock, portMAX_DELAY);
        state.connected = true;
        snprintf(state.ip, sizeof state.ip, IPSTR, IP2STR(&event->ip_info.ip));
        xSemaphoreGive(lock);
        ESP_LOGI(TAG, "got address %s", state.ip);
    }
}

void net_note_hub(int status)
{
    wifi_ap_record_t ap;
    int rssi = esp_wifi_sta_get_ap_info(&ap) == ESP_OK ? ap.rssi : 0;
    xSemaphoreTake(lock, portMAX_DELAY);
    state.rssi = rssi;
    state.hub_status = status;
    xSemaphoreGive(lock);
}

void net_start(void)
{
    lock = xSemaphoreCreateMutex();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL));

    wifi_config_t config = {0};
    strlcpy((char *)config.sta.ssid, CONFIG_PANEL_WIFI_SSID, sizeof config.sta.ssid);
    strlcpy((char *)config.sta.password, CONFIG_PANEL_WIFI_PASSWORD, sizeof config.sta.password);
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    ESP_ERROR_CHECK(esp_wifi_start());
}
