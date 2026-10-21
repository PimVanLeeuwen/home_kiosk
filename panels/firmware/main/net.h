#pragma once

#include <stdbool.h>

/* What the network side knows, for the screen. Written by the Wi-Fi and hub
 * tasks, read by the screen once a second; small enough to copy whole. */
typedef struct {
    bool connected;
    bool no_network;      /* no Wi-Fi network saved on this board */
    char ip[16];
    int rssi;             /* dBm, 0 when not connected */
    int hub_status;       /* HTTP status of the last /api/desk call, 0 before the first */
    int disconnects;
} net_state_t;

void net_start(void);
net_state_t net_state(void);
/* The status of the last /api/desk call, with the signal at that moment. */
void net_note_hub(int status);
/* The hub has answered before but not for a minute: the panel says so and stops
 * turning (plan.md open items, 2026-10-21). */
bool net_hub_away(void);
