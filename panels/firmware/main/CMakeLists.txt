idf_component_register(SRCS "main.c" "net.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi esp_netif esp_http_client nvs_flash esp_event)
