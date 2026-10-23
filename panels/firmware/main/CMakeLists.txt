idf_component_register(SRCS "main.c" "net.c" "desk.c" "screens.c" "screen_clock.c" "screen_day.c" "screen_train.c" "screen_agenda.c" "screen_headlines.c" "screen_lights.c" "screen_playing.c" "screen_music.c" "screen_air.c" "screen_pipeline.c" "screen_pipelines.c" "desk_pipelines.c" "screen_code.c" "desk_code.c" "screen_sites.c" "desk_sites.c" "screen_services.c" "desk_services.c" "screen_tailnet.c" "desk_tailnet.c" "screen_alerts.c" "desk_alerts.c" "screen_nas.c" "desk_nas.c" "screen_backups.c" "desk_backups.c" "screen_media.c" "desk_media.c" "screen_money.c" "desk_money.c" "screen_movers.c" "desk_movers.c" "screen_laundry.c" "screen_apple.c" "icons.c" "screen_board.c" "pictures.c" "actions.c" "screen_start.c" "devshot.c" "update.c" "health.c" "lvgl_memory.c" "ui.c" "takeover.c"
                            "fonts/instrument_clock.c" "fonts/instrument_40.c"
                            "fonts/instrument_28_bold.c" "fonts/instrument_24.c"
                            "fonts/instrument_time.c" "fonts/instrument_52_bold.c"
                            "images/glow_sky.c" "images/glow_round.c" "images/logos.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_netif esp_http_client nvs_flash esp_event json esp_app_format app_update esp_timer esp_driver_jpeg
                       # LVGL calls lvgl_memory.c, which nothing in main calls.
                       WHOLE_ARCHIVE)
