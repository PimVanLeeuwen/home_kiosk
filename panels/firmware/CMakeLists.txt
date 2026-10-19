# The desk panels' firmware (plan.md M16): one build for all three panels.
cmake_minimum_required(VERSION 3.16)

# Shared settings, then the Wi-Fi secrets from an untracked file when it exists
# (CI writes the same file from a GitHub Actions secret).
set(SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults")
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.secrets")
    list(APPEND SDKCONFIG_DEFAULTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.secrets")
endif()

# The firmware version the boards report to the hub: the commit it was built
# from (PANEL_VERSION, set by CI and the build command), else "dev".
if(DEFINED ENV{PANEL_VERSION})
    set(PROJECT_VER "$ENV{PANEL_VERSION}")
else()
    set(PROJECT_VER "dev")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(desk_panel)
