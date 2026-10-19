idf_component_register(SRCS "main.c" "net.c" "desk.c" "screen_clock.c" "devshot.c"
                            "fonts/instrument_clock.c" "fonts/instrument_40.c"
                            "fonts/instrument_28_bold.c" "fonts/instrument_24.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_netif esp_http_client nvs_flash esp_event json)
