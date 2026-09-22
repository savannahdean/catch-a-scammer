#include "theme.h"

#include <algorithm>
#include <cstdio>
#include <sstream>
#include <vector>

namespace theme {
namespace {

Font g_ui;
Font g_mono;
bool g_loaded = false;

const char* kUiCandidates[] = {
    "assets/ui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
};

const char* kMonoCandidates[] = {
    "assets/mono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
};

Font TryLoad(const char* const* candidates, int n, int size) {
    for (int i = 0; i < n; ++i) {
        if (FileExists(candidates[i])) {
            Font f = LoadFontEx(candidates[i], size, nullptr, 0);
            if (f.texture.id != 0) {
                SetTextureFilter(f.texture, TEXTURE_FILTER_BILINEAR);
                return f;
            }
        }
    }
    return GetFontDefault();
}

}  // namespace

void LoadFonts() {
    if (g_loaded) return;
    g_ui = TryLoad(kUiCandidates, (int)(sizeof(kUiCandidates) / sizeof(char*)), 32);
    g_mono = TryLoad(kMonoCandidates, (int)(sizeof(kMonoCandidates) / sizeof(char*)), 32);
    g_loaded = true;
}

void UnloadFonts() {
    if (!g_loaded) return;
    if (g_ui.texture.id != GetFontDefault().texture.id) UnloadFont(g_ui);
    if (g_mono.texture.id != GetFontDefault().texture.id) UnloadFont(g_mono);
    g_loaded = false;
}

const Font& UI() { return g_ui; }
const Font& Mono() { return g_mono; }

float TextW(const Font& f, const std::string& s, float size) {
    return MeasureTextEx(f, s.c_str(), size, 1.0f).x;
}

void Text(const Font& f, const std::string& s, float x, float y, float size, Color c) {
    DrawTextEx(f, s.c_str(), Vector2{x, y}, size, 1.0f, c);
}

float TextWrapped(const Font& f, const std::string& s, Rectangle box, float size,
                  Color c, bool draw) {
    const float lineH = size * 1.32f;
    float y = box.y;

    std::istringstream all(s);
    std::string rawLine;
    while (std::getline(all, rawLine)) {
        // preserve leading indentation, which the briefings rely on
        size_t indent = rawLine.find_first_not_of(' ');
        std::string pad = (indent == std::string::npos)
                              ? std::string()
                              : rawLine.substr(0, indent);
        std::istringstream words(rawLine);
        std::string word, line = pad;
        bool first = true;
        auto flush = [&]() {
            if (draw && y + lineH >= box.y && y <= box.y + box.height)
                Text(f, line, box.x, y, size, c);
            y += lineH;
            line = pad;
            first = true;
        };
        while (words >> word) {
            std::string trial = first ? line + word : line + " " + word;
            if (!first && TextW(f, trial, size) > box.width) {
                flush();
                trial = line + word;
            }
            line = trial;
            first = false;
        }
        flush();
    }
    return y - box.y;
}

Color StatusColor(const std::string& status) {
    if (status == "malicious") return DANGER;
    if (status == "suspicious") return WARN;
    if (status == "benign") return OK;
    return TEXT_DIM;
}

}  // namespace theme
