// catch-a-scammer -- game client
//
// Boots a window, hands every frame to the fake operating system, and tears
// the networking stack down on the way out. All of the interesting behaviour
// lives in Desktop and the App implementations.

#include <raylib.h>

#include <cstdio>
#include <cstring>
#include <string>

#include "core/theme.h"
#include "net/http.h"
#include "os/desktop.h"

namespace {

constexpr int kDefaultWidth = 1440;
constexpr int kDefaultHeight = 900;
constexpr int kMinWidth = 1100;
constexpr int kMinHeight = 700;

void PrintUsage() {
    std::printf(
        "catch-a-scammer client\n"
        "\n"
        "  --api <url>       case service base URL (default $CAS_API or\n"
        "                    http://127.0.0.1:8000)\n"
        "  --player <name>   name recorded on submissions (default $CAS_PLAYER)\n"
        "  --windowed        start windowed at %dx%d (default)\n"
        "  --fullscreen      start fullscreen on the primary display\n"
        "  --help            this message\n",
        kDefaultWidth, kDefaultHeight);
}

}  // namespace

int main(int argc, char** argv) {
    std::string apiOverride;
    std::string playerOverride;
    bool fullscreen = false;

    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--api") == 0 && i + 1 < argc) {
            apiOverride = argv[++i];
        } else if (std::strcmp(argv[i], "--player") == 0 && i + 1 < argc) {
            playerOverride = argv[++i];
        } else if (std::strcmp(argv[i], "--fullscreen") == 0) {
            fullscreen = true;
        } else if (std::strcmp(argv[i], "--windowed") == 0) {
            fullscreen = false;
        } else if (std::strcmp(argv[i], "--help") == 0 ||
                   std::strcmp(argv[i], "-h") == 0) {
            PrintUsage();
            return 0;
        } else {
            std::printf("unrecognised argument: %s\n\n", argv[i]);
            PrintUsage();
            return 2;
        }
    }

    net::GlobalInit();

    SetTraceLogLevel(LOG_WARNING);
    SetConfigFlags(FLAG_WINDOW_RESIZABLE | FLAG_MSAA_4X_HINT | FLAG_VSYNC_HINT);
    InitWindow(kDefaultWidth, kDefaultHeight, "catch-a-scammer");
    SetWindowMinSize(kMinWidth, kMinHeight);
    SetExitKey(KEY_NULL);  // ESC closes overlays, it does not close the game
    SetTargetFPS(60);

    if (fullscreen) {
        int display = GetCurrentMonitor();
        SetWindowSize(GetMonitorWidth(display), GetMonitorHeight(display));
        ToggleFullscreen();
    }

    theme::LoadFonts();

    {
        // Desktop owns the Session, so scope it: everything is released
        // before the window and curl go away.
        Desktop desktop;
        if (!apiOverride.empty()) desktop.session().apiBase = apiOverride;
        if (!playerOverride.empty()) desktop.session().playerName = playerOverride;
        desktop.session().pingHealth();

        while (!WindowShouldClose() && !desktop.wantsQuit()) {
            float dt = GetFrameTime();

            if (IsKeyPressed(KEY_F11)) {
                ToggleFullscreen();
            }

            desktop.Update(dt);

            BeginDrawing();
            ClearBackground(theme::DESKTOP_BOTTOM);
            desktop.Draw();
            EndDrawing();
        }
    }

    theme::UnloadFonts();
    CloseWindow();
    net::GlobalShutdown();
    return 0;
}
