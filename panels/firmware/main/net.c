/* Wi-Fi through the ESP32-C6 with ESP-Hosted (the esp_wifi API is the same).
 * The hub is asked in desk.c, which reports its answers here.
 *
 * The network's name and password live in the board's own storage (NVS), which
 * updates over Wi-Fi leave alone: a local build that carries them (from the
 * untracked sdkconfig.secrets) saves them there at its first start, and the
 * build CI makes for every board carries none, as it ships in a public image.
 *
 * A watchdog keeps the board on the hub (2026-10-21: the Home board fell away for
 * hours and only came back when the nightly update restarted it): without an
 * answer for 2 minutes it reconnects Wi-Fi, for 5 minutes it restarts the board.
 * After such a restart it waits 10 minutes before the next one, so a hub that is
 * down for long does not make the panels restart all the time. */

#include "net.h"

#include <stdio.h>
#include <string.h>

#include "esp_attr.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"
#include "sdkconfig.h"
#include "update.h"

static const char *TAG = "net";
static net_state_t state;
static SemaphoreHandle_t lock;

#define AWAY_US (60LL * 1000000)           /* no answer this long: say so on the panel */
#define RECONNECT_US (2LL * 60 * 1000000)  /* then reconnect Wi-Fi */
#define RESTART_US (5LL * 60 * 1000000)    /* then restart the board */
#define AGAIN_US (10LL * 60 * 1000000)     /* ... or this long after the watchdog restarted it */
#define RESTART_MAGIC 0x6875622a

static int64_t last_answer_us;  /* the hub's last 200, esp_timer time; 0 before the first */
static int64_t reconnected_us;  /* when the watchdog last reconnected Wi-Fi in this outage */
/* Kept over a restart (not over power off): whether the watchdog restarted the board. */
RTC_NOINIT_ATTR static uint32_t restarted_magic;

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
    if (status == 200) {
        if (last_answer_us && esp_timer_get_time() - last_answer_us > AWAY_US) {
            ESP_LOGI(TAG, "the hub answers again after %lld s",
                     (esp_timer_get_time() - last_answer_us) / 1000000);
        }
        last_answer_us = esp_timer_get_time();
        reconnected_us = 0;
        restarted_magic = 0; /* a later outage may restart it again after 5 minutes */
    }
    xSemaphoreGive(lock);
}

bool net_hub_away(void)
{
    if (lock == NULL) {
        return false;
    }
    xSemaphoreTake(lock, portMAX_DELAY);
    bool away = last_answer_us && esp_timer_get_time() - last_answer_us > AWAY_US;
    xSemaphoreGive(lock);
    return away;
}

/* Every 10 s: how long since the hub answered, and what to do about it. The clock
 * starts at boot, so a board that never reaches the hub restarts too. */
static void watchdog_task(void *arg)
{
    int64_t since_boot_start = esp_timer_get_time();
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        if (update_busy()) {
            continue; /* installing: no polls meanwhile */
        }
        xSemaphoreTake(lock, portMAX_DELAY);
        int64_t now = esp_timer_get_time();
        int64_t quiet = now - (last_answer_us ? last_answer_us : since_boot_start);
        net_state_t s = state;
        bool reconnect = quiet > RECONNECT_US && !reconnected_us;
        if (reconnect) {
            reconnected_us = now;
        }
        xSemaphoreGive(lock);

        int64_t restart_after = restarted_magic == RESTART_MAGIC ? AGAIN_US : RESTART_US;
        if (quiet > restart_after) {
            ESP_LOGW(TAG, "no answer from the hub for %lld s (last status %d, Wi-Fi %s, %d dBm): restarting",
                     quiet / 1000000, s.hub_status, s.connected ? "connected" : "down", s.rssi);
            restarted_magic = RESTART_MAGIC;
            vTaskDelay(pdMS_TO_TICKS(500)); /* let the log out */
            esp_restart();
        }
        if (reconnect) {
            ESP_LOGW(TAG, "no answer from the hub for %lld s (last status %d, Wi-Fi %s, %d dBm): reconnecting Wi-Fi",
                     quiet / 1000000, s.hub_status, s.connected ? "connected" : "down", s.rssi);
            esp_wifi_disconnect(); /* the disconnect event connects again */
            if (!s.connected) {
                esp_wifi_connect();
            }
        }
    }
}

/* The network from this build if it has one (saved for later builds), else
 * the one saved before. False when the board has never been given one. */
static bool credentials(wifi_config_t *config)
{
    char *ssid = (char *)config->sta.ssid, *password = (char *)config->sta.password;
    nvs_handle_t nvs;
    if (nvs_open("wifi", NVS_READWRITE, &nvs) != ESP_OK) {
        return false;
    }
    bool found;
    if (CONFIG_PANEL_WIFI_SSID[0] != '\0') {
        strlcpy(ssid, CONFIG_PANEL_WIFI_SSID, sizeof config->sta.ssid);
        strlcpy(password, CONFIG_PANEL_WIFI_PASSWORD, sizeof config->sta.password);
        nvs_set_str(nvs, "ssid", ssid);
        nvs_set_str(nvs, "password", password);
        nvs_commit(nvs);
        found = true;
    } else {
        size_t ssid_size = sizeof config->sta.ssid, password_size = sizeof config->sta.password;
        found = nvs_get_str(nvs, "ssid", ssid, &ssid_size) == ESP_OK &&
                nvs_get_str(nvs, "password", password, &password_size) == ESP_OK;
    }
    nvs_close(nvs);
    return found;
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
    if (!credentials(&config)) {
        /* Flash this board once over USB with a build that has sdkconfig.secrets. */
        ESP_LOGE(TAG, "no Wi-Fi network saved on this board");
        xSemaphoreTake(lock, portMAX_DELAY);
        state.no_network = true;
        xSemaphoreGive(lock);
        return;
    }
    config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    ESP_ERROR_CHECK(esp_wifi_start());
    if (esp_reset_reason() != ESP_RST_SW) {
        restarted_magic = 0; /* power on: the RTC memory holds noise */
    }
    xTaskCreate(watchdog_task, "watchdog", 3072, NULL, 2, NULL);
}
