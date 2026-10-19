idf_component_register(SRCS "main.c" "net.c" "desk.c" "screens.c" "screen_clock.c" "screen_day.c" "screen_board.c" "screen_start.c" "devshot.c" "update.c"
                            "fonts/instrument_clock.c" "fonts/instrument_40.c"
                            "fonts/instrument_28_bold.c" "fonts/instrument_24.c"
                            "images/glow_sky.c" "images/glow_round.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_netif esp_http_client nvs_flash esp_event json esp_app_format app_update esp_timer)
