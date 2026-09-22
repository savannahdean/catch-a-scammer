#pragma once
#include <raylib.h>

#include <functional>
#include <string>
#include <vector>

// A very small immediate-mode toolkit. Every widget draws and handles its own
// input in one call. Input is globally gated so only the focused window reacts.
namespace ui {

void SetEnabled(bool enabled);
bool Enabled();

bool Hover(Rectangle r);
bool Clicked(Rectangle r);

void Panel(Rectangle r, Color bg, Color edge);
void Bevel(Rectangle r, bool sunken);
void Divider(float x, float y, float w);
void SectionLabel(const std::string& text, float x, float y);
void KeyValue(const std::string& key, const std::string& value, float x, float y,
              float keyWidth, Color valueColor);
void Badge(Rectangle r, const std::string& text, Color bg);

bool Button(Rectangle r, const std::string& label, bool enabled = true);
bool TinyButton(Rectangle r, const std::string& label, bool enabled = true);
bool Checkbox(Rectangle r, const std::string& label, bool& value);

struct TextField {
    std::string text;
    bool focus = false;
    float repeat = 0.0f;
};
// Returns true when the user presses Enter.
bool TextFieldW(TextField& tf, Rectangle r, const std::string& placeholder);

struct Scroll {
    float y = 0.0f;
    float content = 0.0f;
};
// Call Begin, draw content offset by -s.y, then End with the real height.
void BeginScroll(Scroll& s, Rectangle view);
void EndScroll(Scroll& s, Rectangle view, float contentHeight);

bool Row(Rectangle r, const std::string& text, const std::string& right,
         bool selected, Color accent);

struct Combo {
    int index = -1;
    bool open = false;
    Scroll scroll;
};
// Returns true when the selection changes.
bool ComboW(Combo& c, Rectangle r, const std::vector<std::string>& items,
            const std::string& placeholder);

// Popups (combo lists, tooltips) must paint above the rest of the window, so
// they are queued here and flushed after the window content is drawn.
void DeferPopup(std::function<void()> fn);
void FlushPopups();

void Spinner(Vector2 center, float radius, Color c);

}  // namespace ui
