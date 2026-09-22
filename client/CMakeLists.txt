cmake_minimum_required(VERSION 3.16)
project(catch_a_scammer_client CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

include(FetchContent)

# ---------------------------------------------------------------- raylib ----
# Prefer a system raylib (apt / brew / vcpkg). Fall back to fetching it so a
# teammate with nothing installed can still build with one command.
find_package(raylib 4.5 QUIET)
if(NOT raylib_FOUND)
  message(STATUS "system raylib not found -- fetching 5.0")
  set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
  set(BUILD_GAMES    OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    raylib
    GIT_REPOSITORY https://github.com/raysan5/raylib.git
    GIT_TAG        5.0
    GIT_SHALLOW    TRUE
  )
  FetchContent_MakeAvailable(raylib)
endif()

# ------------------------------------------------------- nlohmann/json ------
find_package(nlohmann_json 3.9 QUIET)
if(NOT nlohmann_json_FOUND)
  message(STATUS "system nlohmann_json not found -- fetching 3.11.3")
  set(JSON_BuildTests OFF CACHE INTERNAL "")
  FetchContent_Declare(
    nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
  )
  FetchContent_MakeAvailable(nlohmann_json)
endif()

# ------------------------------------------------------------- libcurl ------
find_package(CURL REQUIRED)

add_executable(catch-a-scammer
  src/main.cpp
  src/core/session.cpp
  src/core/theme.cpp
  src/net/http.cpp
  src/os/desktop.cpp
  src/ui/widgets.cpp
  src/apps/common.cpp
  src/apps/registry.cpp
  src/apps/apps_case.cpp
  src/apps/apps_lookup.cpp
  src/apps/apps_graph.cpp
)

target_link_libraries(catch-a-scammer PRIVATE raylib nlohmann_json::nlohmann_json CURL::libcurl)

if(APPLE)
  target_link_libraries(catch-a-scammer PRIVATE
    "-framework IOKit" "-framework Cocoa" "-framework OpenGL")
elseif(UNIX)
  find_package(Threads REQUIRED)
  target_link_libraries(catch-a-scammer PRIVATE Threads::Threads ${CMAKE_DL_LIBS} m)
elseif(WIN32)
  target_link_libraries(catch-a-scammer PRIVATE winmm)
endif()

if(MSVC)
  target_compile_options(catch-a-scammer PRIVATE /W3)
else()
  target_compile_options(catch-a-scammer PRIVATE -Wall -Wextra -Wno-unused-parameter)
endif()

# Optional: drop ui.ttf / mono.ttf into client/assets to override the system
# fonts theme.cpp searches for.
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/assets)
  add_custom_command(TARGET catch-a-scammer POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
            ${CMAKE_CURRENT_SOURCE_DIR}/assets
            $<TARGET_FILE_DIR:catch-a-scammer>/assets
    COMMENT "copying assets")
endif()
