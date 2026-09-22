#pragma once
#include <raylib.h>
#include <string>

// The in-game operating system. Change these two strings and the whole shell
// re-brands -- nothing else hardcodes the name.
namespace brand {
inline constexpr const char* OS_NAME = "SLEUTHOS";
inline constexpr const char* OS_VERSION = "7.1";
inline constexpr const char* AGENCY = "DIGITAL INCIDENT RESPONSE UNIT";
}  // namespace brand

namespace theme {

// --- palette -------------------------------------------------------------
inline constexpr Color DESKTOP_TOP    = {14, 32, 48, 255};
inline constexpr Color DESKTOP_BOTTOM = {6, 14, 22, 255};
inline constexpr Color TASKBAR        = {22, 30, 40, 255};
inline constexpr Color TASKBAR_EDGE   = {58, 74, 92, 255};

inline constexpr Color WIN_BODY       = {231, 233, 236, 255};
inline constexpr Color WIN_PANEL      = {245, 246, 248, 255};
inline constexpr Color WIN_BORDER     = {96, 110, 126, 255};
inline constexpr Color TITLE_ACTIVE   = {32, 76, 116, 255};
inline constexpr Color TITLE_IDLE     = {104, 116, 130, 255};
inline constexpr Color TITLE_TEXT     = {245, 248, 252, 255};

inline constexpr Color TEXT           = {26, 32, 40, 255};
inline constexpr Color TEXT_DIM       = {104, 114, 128, 255};
inline constexpr Color TEXT_INVERT    = {236, 240, 246, 255};

inline constexpr Color ACCENT         = {24, 122, 168, 255};
inline constexpr Color ACCENT_DARK    = {16, 86, 122, 255};
inline constexpr Color OK             = {32, 140, 88, 255};
inline constexpr Color WARN           = {192, 132, 24, 255};
inline constexpr Color DANGER         = {178, 48, 48, 255};
inline constexpr Color NOISE          = {126, 106, 156, 255};

inline constexpr Color FIELD_BG       = {255, 255, 255, 255};
inline constexpr Color FIELD_EDGE     = {158, 168, 180, 255};
inline constexpr Color BTN            = {222, 226, 232, 255};
inline constexpr Color BTN_HOVER      = {236, 240, 246, 255};
inline constexpr Color BTN_DOWN       = {198, 206, 216, 255};
inline constexpr Color BTN_EDGE       = {140, 152, 166, 255};

inline constexpr Color TERM_BG        = {12, 20, 26, 255};
inline constexpr Color TERM_TEXT      = {148, 226, 188, 255};

// --- metrics -------------------------------------------------------------
inline constexpr float TITLE_H   = 28.0f;
inline constexpr float TASKBAR_H = 40.0f;
inline constexpr float PAD       = 10.0f;
inline constexpr float ROW_H     = 26.0f;

// --- fonts ---------------------------------------------------------------
// Loaded once at startup. If no TTF is found on the system we fall back to
// raylib's built-in font, which is ugly but always present.
void LoadFonts();
void UnloadFonts();
const Font& UI();      // proportional-ish body font
const Font& Mono();    // used for records, addresses, hashes

float TextW(const Font& f, const std::string& s, float size);
void  Text(const Font& f, const std::string& s, float x, float y, float size, Color c);

// Word-wraps and returns the height consumed. Pass draw=false to measure.
float TextWrapped(const Font& f, const std::string& s, Rectangle box,
                  float size, Color c, bool draw = true);

Color StatusColor(const std::string& status);

}  // namespace theme
