#include "widgets.h"

#include <algorithm>
#include <cmath>

#include "../core/theme.h"

namespace ui {
namespace {
bool g_enabled = true;
std::vector<std::function<void()>> g_popups;
}  // namespace

void SetEnabled(bool enabled) { g_enabled = enabled; }
bool Enabled() { return g_enabled; }

bool Hover(Rectangle r) {
    return g_enabled && CheckCollisionPointRec(GetMousePosition(), r);
}

bool Clicked(Rectangle r) {
    return Hover(r) && IsMouseButtonPressed(MOUSE_BUTTON_LEFT);
}

void Panel(Rectangle r, Color bg, Color edge) {
    DrawRectangleRec(r, bg);
    DrawRectangleLinesEx(r, 1.0f, edge);
}

void Bevel(Rectangle r, bool sunken) {
    Color hi = sunken ? Color{120, 130, 142, 255} : Color{255, 255, 255, 220};
    Color lo = sunken ? Color{255, 255, 255, 200} : Color{120, 130, 142, 255};
    DrawLineEx({r.x, r.y}, {r.x + r.width, r.y}, 1.0f, hi);
    DrawLineEx({r.x, r.y}, {r.x, r.y + r.height}, 1.0f, hi);
    DrawLineEx({r.x, r.y + r.height}, {r.x + r.width, r.y + r.height}, 1.0f, lo);
    DrawLineEx({r.x + r.width, r.y}, {r.x + r.width, r.y + r.height}, 1.0f, lo);
}

void Divider(float x, float y, float w) {
    DrawLineEx({x, y}, {x + w, y}, 1.0f, Color{206, 212, 220, 255});
}

void SectionLabel(const std::string& text, float x, float y) {
    theme::Text(theme::UI(), text, x, y, 13.0f, theme::ACCENT_DARK);
    float w = theme::TextW(theme::UI(), text, 13.0f);
    DrawLineEx({x, y + 16.0f}, {x + w, y + 16.0f}, 1.0f, theme::ACCENT);
}

void KeyValue(const std::string& key, const std::string& value, float x, float y,
              float keyWidth, Color valueColor) {
    theme::Text(theme::UI(), key, x, y, 14.0f, theme::TEXT_DIM);
    theme::Text(theme::Mono(), value, x + keyWidth, y, 14.0f, valueColor);
}

void Badge(Rectangle r, const std::string& text, Color bg) {
    DrawRectangleRounded(r, 0.35f, 6, bg);
    float w = theme::TextW(theme::UI(), text, 12.0f);
    theme::Text(theme::UI(), text, r.x + (r.width - w) * 0.5f,
                r.y + (r.height - 12.0f) * 0.5f - 1.0f, 12.0f, theme::TEXT_INVERT);
}

static bool ButtonImpl(Rectangle r, const std::string& label, bool enabled,
                       float fontSize) {
    bool hover = enabled && Hover(r);
    bool down = hover && IsMouseButtonDown(MOUSE_BUTTON_LEFT);
    Color bg = !enabled ? Color{226, 228, 232, 255}
                        : down ? theme::BTN_DOWN : hover ? theme::BTN_HOVER : theme::BTN;
    DrawRectangleRec(r, bg);
    DrawRectangleLinesEx(r, 1.0f, enabled ? theme::BTN_EDGE
                                          : Color{200, 204, 210, 255});
    Bevel(r, down);
    Color fg = enabled ? theme::TEXT : theme::TEXT_DIM;
    float w = theme::TextW(theme::UI(), label, fontSize);
    theme::Text(theme::UI(), label, r.x + (r.width - w) * 0.5f,
                r.y + (r.height - fontSize) * 0.5f, fontSize, fg);
    return enabled && hover && IsMouseButtonPressed(MOUSE_BUTTON_LEFT);
}

bool Button(Rectangle r, const std::string& label, bool enabled) {
    return ButtonImpl(r, label, enabled, 14.0f);
}

bool TinyButton(Rectangle r, const std::string& label, bool enabled) {
    return ButtonImpl(r, label, enabled, 12.0f);
}

bool Checkbox(Rectangle r, const std::string& label, bool& value) {
    Rectangle box{r.x, r.y + (r.height - 16.0f) * 0.5f, 16.0f, 16.0f};
    DrawRectangleRec(box, theme::FIELD_BG);
    DrawRectangleLinesEx(box, 1.0f, theme::FIELD_EDGE);
    if (value) {
        DrawLineEx({box.x + 3, box.y + 8}, {box.x + 7, box.y + 12}, 2.0f, theme::ACCENT);
        DrawLineEx({box.x + 7, box.y + 12}, {box.x + 13, box.y + 4}, 2.0f, theme::ACCENT);
    }
    theme::Text(theme::UI(), label, box.x + 24.0f,
                r.y + (r.height - 14.0f) * 0.5f, 14.0f, theme::TEXT);
    if (Clicked(r)) {
        value = !value;
        return true;
    }
    return false;
}

bool TextFieldW(TextField& tf, Rectangle r, const std::string& placeholder) {
    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT))
        tf.focus = Hover(r);
    if (!g_enabled) tf.focus = false;

    DrawRectangleRec(r, theme::FIELD_BG);
    DrawRectangleLinesEx(r, tf.focus ? 2.0f : 1.0f,
                         tf.focus ? theme::ACCENT : theme::FIELD_EDGE);

    bool submitted = false;
    if (tf.focus) {
        int ch = GetCharPressed();
        while (ch > 0) {
            if (ch >= 32 && ch <= 126 && tf.text.size() < 180)
                tf.text.push_back((char)ch);
            ch = GetCharPressed();
        }
        // backspace with key repeat
        if (IsKeyPressed(KEY_BACKSPACE)) {
            if (!tf.text.empty()) tf.text.pop_back();
            tf.repeat = -0.35f;
        } else if (IsKeyDown(KEY_BACKSPACE)) {
            tf.repeat += GetFrameTime();
            if (tf.repeat > 0.04f) {
                tf.repeat = 0.0f;
                if (!tf.text.empty()) tf.text.pop_back();
            }
        } else {
            tf.repeat = 0.0f;
        }
        if ((IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL)) &&
            IsKeyPressed(KEY_V)) {
            const char* clip = GetClipboardText();
            if (clip) tf.text += clip;
        }
        if (IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_KP_ENTER)) submitted = true;
    }

    const float fs = 15.0f;
    BeginScissorMode((int)r.x + 4, (int)r.y, (int)r.width - 8, (int)r.height);
    if (tf.text.empty() && !tf.focus) {
        theme::Text(theme::UI(), placeholder, r.x + 8.0f,
                    r.y + (r.height - fs) * 0.5f, fs, theme::TEXT_DIM);
    } else {
        float w = theme::TextW(theme::Mono(), tf.text, fs);
        float shift = std::max(0.0f, w - (r.width - 20.0f));
        theme::Text(theme::Mono(), tf.text, r.x + 8.0f - shift,
                    r.y + (r.height - fs) * 0.5f, fs, theme::TEXT);
        if (tf.focus && fmodf((float)GetTime(), 1.0f) < 0.5f) {
            float cx = r.x + 8.0f - shift + w + 1.0f;
            DrawLineEx({cx, r.y + 5}, {cx, r.y + r.height - 5}, 1.0f, theme::TEXT);
        }
    }
    EndScissorMode();
    return submitted;
}

void BeginScroll(Scroll& s, Rectangle view) {
    if (Hover(view)) {
        float wheel = GetMouseWheelMove();
        if (wheel != 0.0f) s.y -= wheel * 42.0f;
    }
    BeginScissorMode((int)view.x, (int)view.y, (int)view.width, (int)view.height);
}

void EndScroll(Scroll& s, Rectangle view, float contentHeight) {
    EndScissorMode();
    s.content = contentHeight;
    float maxScroll = std::max(0.0f, contentHeight - view.height);
    s.y = std::min(std::max(s.y, 0.0f), maxScroll);
    if (maxScroll <= 0.0f) return;

    Rectangle track{view.x + view.width - 10.0f, view.y, 10.0f, view.height};
    DrawRectangleRec(track, Color{222, 226, 232, 255});
    float ratio = view.height / contentHeight;
    float thumbH = std::max(28.0f, view.height * ratio);
    float t = s.y / maxScroll;
    Rectangle thumb{track.x + 2.0f, track.y + t * (view.height - thumbH), 6.0f, thumbH};
    DrawRectangleRounded(thumb, 0.5f, 4, Color{146, 158, 172, 255});

    if (Hover(track) && IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
        float rel = (GetMousePosition().y - track.y - thumbH * 0.5f) /
                    std::max(1.0f, (view.height - thumbH));
        s.y = std::min(std::max(rel, 0.0f), 1.0f) * maxScroll;
    }
}

bool Row(Rectangle r, const std::string& text, const std::string& right,
         bool selected, Color accent) {
    bool hover = Hover(r);
    if (selected)
        DrawRectangleRec(r, Color{(unsigned char)accent.r, (unsigned char)accent.g,
                                  (unsigned char)accent.b, 40});
    else if (hover)
        DrawRectangleRec(r, Color{0, 0, 0, 12});
    DrawLineEx({r.x, r.y + r.height}, {r.x + r.width, r.y + r.height}, 1.0f,
               Color{224, 228, 234, 255});
    if (selected)
        DrawRectangleRec({r.x, r.y, 3.0f, r.height}, accent);

    BeginScissorMode((int)r.x, (int)r.y, (int)r.width, (int)r.height);
    theme::Text(theme::Mono(), text, r.x + 12.0f, r.y + (r.height - 14.0f) * 0.5f,
                14.0f, theme::TEXT);
    if (!right.empty()) {
        float w = theme::TextW(theme::UI(), right, 12.0f);
        theme::Text(theme::UI(), right, r.x + r.width - w - 14.0f,
                    r.y + (r.height - 12.0f) * 0.5f, 12.0f, accent);
    }
    EndScissorMode();
    return hover && IsMouseButtonPressed(MOUSE_BUTTON_LEFT);
}

bool ComboW(Combo& c, Rectangle r, const std::vector<std::string>& items,
            const std::string& placeholder) {
    DrawRectangleRec(r, theme::FIELD_BG);
    DrawRectangleLinesEx(r, 1.0f, c.open ? theme::ACCENT : theme::FIELD_EDGE);

    std::string label = (c.index >= 0 && c.index < (int)items.size())
                            ? items[c.index] : placeholder;
    Color fg = (c.index >= 0) ? theme::TEXT : theme::TEXT_DIM;
    BeginScissorMode((int)r.x, (int)r.y, (int)r.width - 24, (int)r.height);
    theme::Text(theme::Mono(), label, r.x + 8.0f, r.y + (r.height - 14.0f) * 0.5f,
                14.0f, fg);
    EndScissorMode();

    Rectangle arrow{r.x + r.width - 22.0f, r.y + 1.0f, 21.0f, r.height - 2.0f};
    DrawRectangleRec(arrow, theme::BTN);
    DrawTriangle({arrow.x + 6, arrow.y + arrow.height * 0.42f},
                 {arrow.x + 15, arrow.y + arrow.height * 0.42f},
                 {arrow.x + 10.5f, arrow.y + arrow.height * 0.62f}, theme::TEXT);

    if (Clicked(r)) c.open = !c.open;

    bool changed = false;
    if (c.open && !items.empty()) {
        float rowH = 24.0f;
        float h = std::min(rowH * items.size(), 200.0f);
        Rectangle list{r.x, r.y + r.height, r.width, h};
        // hit-test now so the click is not swallowed by widgets drawn after us
        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT) && Hover(list)) {
            int idx = (int)((GetMousePosition().y - list.y + c.scroll.y) / rowH);
            if (idx >= 0 && idx < (int)items.size()) {
                c.index = idx;
                c.open = false;
                changed = true;
            }
        } else if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT) && !Hover(r)) {
            c.open = false;
        }
        Combo* self = &c;
        std::vector<std::string> copy = items;
        DeferPopup([list, copy, rowH, self]() {
            DrawRectangleRec({list.x + 3, list.y + 3, list.width, list.height},
                             Color{0, 0, 0, 50});
            Panel(list, theme::WIN_PANEL, theme::FIELD_EDGE);
            BeginScissorMode((int)list.x, (int)list.y, (int)list.width,
                             (int)list.height);
            for (size_t i = 0; i < copy.size(); ++i) {
                Rectangle rr{list.x, list.y + i * rowH - self->scroll.y,
                             list.width, rowH};
                if (rr.y + rowH < list.y || rr.y > list.y + list.height) continue;
                if (CheckCollisionPointRec(GetMousePosition(), rr))
                    DrawRectangleRec(rr, Color{24, 122, 168, 36});
                if ((int)i == self->index)
                    DrawRectangleRec({rr.x, rr.y, 3, rr.height}, theme::ACCENT);
                theme::Text(theme::Mono(), copy[i], rr.x + 10.0f, rr.y + 5.0f, 13.0f,
                            theme::TEXT);
            }
            EndScissorMode();
            float maxS = std::max(0.0f, rowH * copy.size() - list.height);
            if (CheckCollisionPointRec(GetMousePosition(), list))
                self->scroll.y = std::min(std::max(self->scroll.y -
                                                   GetMouseWheelMove() * 40.0f,
                                                   0.0f), maxS);
        });
    }
    return changed;
}

void DeferPopup(std::function<void()> fn) { g_popups.push_back(std::move(fn)); }

void FlushPopups() {
    for (auto& fn : g_popups) fn();
    g_popups.clear();
}

void Spinner(Vector2 center, float radius, Color c) {
    float t = (float)GetTime() * 3.0f;
    for (int i = 0; i < 8; ++i) {
        float a = t + i * (PI / 4.0f);
        unsigned char alpha = (unsigned char)(255 * (i / 8.0f));
        DrawCircleV({center.x + cosf(a) * radius, center.y + sinf(a) * radius},
                    radius * 0.18f, Color{c.r, c.g, c.b, alpha});
    }
}

}  // namespace ui
