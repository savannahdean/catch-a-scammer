#include "desktop.h"

#include <algorithm>
#include <cmath>
#include <ctime>

#include "../core/theme.h"
#include "../ui/widgets.h"

namespace {

constexpr float ICON_W = 92.0f;
constexpr float ICON_H = 84.0f;
constexpr float BOOT_SECONDS = 2.6f;

std::string Clock12() {
    std::time_t t = std::time(nullptr);
    std::tm lt{};
#ifdef _WIN32
    localtime_s(&lt, &t);
#else
    localtime_r(&t, &lt);
#endif
    char buf[32];
    std::strftime(buf, sizeof(buf), "%I:%M %p", &lt);
    return buf;
}

std::string DateShort() {
    std::time_t t = std::time(nullptr);
    std::tm lt{};
#ifdef _WIN32
    localtime_s(&lt, &t);
#else
    localtime_r(&t, &lt);
#endif
    char buf[32];
    std::strftime(buf, sizeof(buf), "%a %d %b", &lt);
    return buf;
}

}  // namespace

Desktop::Desktop() {
    apps_ = MakeApps();
    wins_.resize(apps_.size());
    for (size_t i = 0; i < apps_.size(); ++i) {
        Vector2 sz = apps_[i]->DefaultSize();
        wins_[i].appIndex = (int)i;
        wins_[i].rect = Rectangle{60.0f + 26.0f * i, 50.0f + 22.0f * i, sz.x, sz.y};
    }
    session_.pingHealth();
}

int Desktop::FindApp(const std::string& id) const {
    for (size_t i = 0; i < apps_.size(); ++i)
        if (apps_[i]->Id() == id) return (int)i;
    return -1;
}

void Desktop::OpenApp(const std::string& id, const std::string& query) {
    int i = FindApp(id);
    if (i < 0) return;
    if (apps_[i]->RequiresCase() && !session_.hasCase()) {
        session_.notify("Open a case in CaseDesk first.", true);
        OpenApp("casedesk", "");
        return;
    }
    Win& w = wins_[i];
    if (!w.open) {
        // keep the window on screen if the display shrank since last time
        w.rect.width = std::min(w.rect.width, (float)GetScreenWidth() - 40.0f);
        w.rect.height = std::min(w.rect.height,
                                 (float)GetScreenHeight() - theme::TASKBAR_H - 40.0f);
        w.rect.x = std::min(std::max(w.rect.x, 0.0f),
                            GetScreenWidth() - w.rect.width);
        w.rect.y = std::min(std::max(w.rect.y, 0.0f),
                            GetScreenHeight() - theme::TASKBAR_H - w.rect.height);
    }
    w.open = true;
    w.minimized = false;
    Raise(i);
    apps_[i]->OnOpen(session_, query);
}

void Desktop::Raise(int winIndex) {
    order_.erase(std::remove(order_.begin(), order_.end(), winIndex), order_.end());
    order_.push_back(winIndex);
}

int Desktop::TopWindowAt(Vector2 p) const {
    for (auto it = order_.rbegin(); it != order_.rend(); ++it) {
        const Win& w = wins_[*it];
        if (!w.open || w.minimized) continue;
        Rectangle full{w.rect.x, w.rect.y - theme::TITLE_H, w.rect.width,
                       w.rect.height + theme::TITLE_H};
        if (CheckCollisionPointRec(p, full)) return *it;
    }
    return -1;
}

void Desktop::Update(float dt) {
    boot_ += dt;
    session_.Update(dt);

    healthTimer_ -= dt;
    if (healthTimer_ <= 0.0f) {
        healthTimer_ = 10.0f;
        session_.pingHealth();
    }

    if (boot_ < BOOT_SECONDS) return;

    OpenRequest req;
    while (session_.popOpenRequest(req)) OpenApp(req.app, req.query);

    if (IsKeyPressed(KEY_F1)) helpOpen_ = !helpOpen_;
    if (IsKeyPressed(KEY_ESCAPE)) {
        if (helpOpen_) helpOpen_ = false;
        else if (startOpen_) startOpen_ = false;
    }

    // click-to-focus happens before any widget sees the click
    if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
        Vector2 m = GetMousePosition();
        bool overChrome = m.y > GetScreenHeight() - theme::TASKBAR_H;
        if (!overChrome && !helpOpen_) {
            int hit = TopWindowAt(m);
            if (hit >= 0 && (order_.empty() || order_.back() != hit)) Raise(hit);
            if (hit >= 0) startOpen_ = false;
        }
    }

    // window dragging / resizing
    int top = order_.empty() ? -1 : order_.back();
    if (top >= 0 && wins_[top].open && !wins_[top].minimized) {
        Win& w = wins_[top];
        Vector2 m = GetMousePosition();
        Rectangle title{w.rect.x, w.rect.y - theme::TITLE_H, w.rect.width,
                        theme::TITLE_H};
        Rectangle grip{w.rect.x + w.rect.width - 16.0f,
                       w.rect.y + w.rect.height - 16.0f, 16.0f, 16.0f};

        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT) && !helpOpen_) {
            if (CheckCollisionPointRec(m, grip)) {
                w.resizing = true;
                w.grab = Vector2{m.x - w.rect.width, m.y - w.rect.height};
            } else if (CheckCollisionPointRec(m, title) &&
                       m.x < title.x + title.width - 84.0f) {
                w.dragging = true;
                w.grab = Vector2{m.x - w.rect.x, m.y - w.rect.y};
            }
        }
        if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) {
            w.dragging = false;
            w.resizing = false;
        }
        if (w.dragging) {
            w.rect.x = m.x - w.grab.x;
            w.rect.y = std::max(theme::TITLE_H, m.y - w.grab.y);
            w.rect.x = std::min(std::max(w.rect.x, -w.rect.width + 120.0f),
                                (float)GetScreenWidth() - 120.0f);
            w.rect.y = std::min(w.rect.y,
                                GetScreenHeight() - theme::TASKBAR_H - 40.0f);
        }
        if (w.resizing) {
            w.rect.width = std::max(520.0f, m.x - w.grab.x);
            w.rect.height = std::max(320.0f, m.y - w.grab.y);
        }
    }
}

void Desktop::Draw() {
    DrawWallpaper();
    if (boot_ < BOOT_SECONDS) {
        DrawBoot();
        return;
    }
    DrawIcons();
    DrawWindows();
    DrawTaskbar();
    if (startOpen_) DrawStartMenu();
    DrawToasts();
    if (helpOpen_) DrawHelp();
    ui::FlushPopups();
}

// ------------------------------------------------------------------- boot

void Desktop::DrawBoot() {
    float w = (float)GetScreenWidth();
    float h = (float)GetScreenHeight();
    std::string name = std::string(brand::OS_NAME) + " " + brand::OS_VERSION;
    float tw = theme::TextW(theme::UI(), name, 44.0f);
    theme::Text(theme::UI(), name, (w - tw) * 0.5f, h * 0.38f, 44.0f,
                Color{220, 232, 244, 255});
    float sw = theme::TextW(theme::UI(), brand::AGENCY, 14.0f);
    theme::Text(theme::UI(), brand::AGENCY, (w - sw) * 0.5f, h * 0.38f + 56.0f,
                14.0f, Color{120, 150, 180, 255});

    Rectangle bar{w * 0.5f - 150.0f, h * 0.58f, 300.0f, 6.0f};
    DrawRectangleRec(bar, Color{32, 48, 64, 255});
    float p = std::min(1.0f, boot_ / BOOT_SECONDS);
    DrawRectangleRec({bar.x, bar.y, bar.width * p, bar.height}, theme::ACCENT);

    const char* lines[] = {"mounting case volumes",
                           "attaching intelligence indexes",
                           "restoring desktop session"};
    int idx = std::min(2, (int)(p * 3.0f));
    float lw = theme::TextW(theme::UI(), lines[idx], 12.0f);
    theme::Text(theme::UI(), lines[idx], (w - lw) * 0.5f, bar.y + 18.0f, 12.0f,
                Color{100, 128, 156, 255});
}

// -------------------------------------------------------------- wallpaper

void Desktop::DrawWallpaper() {
    int w = GetScreenWidth();
    int h = GetScreenHeight();
    DrawRectangleGradientV(0, 0, w, h, theme::DESKTOP_TOP, theme::DESKTOP_BOTTOM);

    // faint concentric rings, like a radar backdrop
    Vector2 c{w * 0.72f, h * 0.42f};
    for (int i = 1; i <= 7; ++i)
        DrawCircleLines((int)c.x, (int)c.y, i * 78.0f, Color{60, 110, 150, 16});
    for (int i = 0; i < 12; ++i) {
        float a = i * (PI / 6.0f);
        DrawLineEx(c, {c.x + cosf(a) * 560.0f, c.y + sinf(a) * 560.0f}, 1.0f,
                   Color{60, 110, 150, 10});
    }

    std::string mark = std::string(brand::OS_NAME) + " " + brand::OS_VERSION;
    theme::Text(theme::UI(), mark, w - theme::TextW(theme::UI(), mark, 16.0f) - 20.0f,
                (float)h - theme::TASKBAR_H - 52.0f, 16.0f,
                Color{110, 140, 170, 90});
    theme::Text(theme::UI(), brand::AGENCY,
                w - theme::TextW(theme::UI(), brand::AGENCY, 11.0f) - 20.0f,
                (float)h - theme::TASKBAR_H - 32.0f, 11.0f,
                Color{110, 140, 170, 70});
}

// ------------------------------------------------------------------ icons

void Desktop::DrawIcons() {
    ui::SetEnabled(true);
    float x = 18.0f;
    float y = 18.0f;
    for (size_t i = 0; i < apps_.size(); ++i) {
        Rectangle cell{x, y, ICON_W, ICON_H};
        bool hover = CheckCollisionPointRec(GetMousePosition(), cell);
        bool sel = iconSelected_ == (int)i;
        if (sel || hover)
            DrawRectangleRounded(cell, 0.12f, 6,
                                 Color{120, 180, 230, (unsigned char)(sel ? 52 : 28)});

        Rectangle box{x + ICON_W * 0.5f - 22.0f, y + 10.0f, 44.0f, 40.0f};
        DrawRectangleRounded(box, 0.18f, 6, Color{236, 240, 246, 245});
        // DrawRectangleRoundedLines changed signature between raylib 5.0 and
        // 5.5; DrawRectangleLinesEx is stable across both.
        DrawRectangleLinesEx(box, 1.0f, apps_[i]->Accent());
        DrawRectangleRec({box.x, box.y, box.width, 7.0f}, apps_[i]->Accent());
        std::string g = apps_[i]->Glyph();
        float gw = theme::TextW(theme::UI(), g, 17.0f);
        theme::Text(theme::UI(), g, box.x + (box.width - gw) * 0.5f,
                    box.y + 15.0f, 17.0f, theme::TEXT);

        std::string cap = apps_[i]->Title();
        size_t dash = cap.find(" - ");
        if (dash != std::string::npos) cap = cap.substr(0, dash);
        float cw = theme::TextW(theme::UI(), cap, 12.0f);
        theme::Text(theme::UI(), cap, x + (ICON_W - cw) * 0.5f, y + 56.0f, 12.0f,
                    Color{222, 232, 242, 255});

        if (hover && IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            iconSelected_ = (int)i;
            OpenApp(apps_[i]->Id(), "");
        }

        y += ICON_H + 6.0f;
        if (y + ICON_H > GetScreenHeight() - theme::TASKBAR_H - 10.0f) {
            y = 18.0f;
            x += ICON_W + 8.0f;
        }
    }
}

// ---------------------------------------------------------------- windows

void Desktop::DrawWindows() {
    int top = order_.empty() ? -1 : order_.back();
    for (int idx : order_) {
        Win& w = wins_[idx];
        if (!w.open || w.minimized) continue;
        App* app = apps_[idx].get();
        bool active = (idx == top) && !helpOpen_ && !startOpen_;

        Rectangle title{w.rect.x, w.rect.y - theme::TITLE_H, w.rect.width,
                        theme::TITLE_H};
        Rectangle frame{w.rect.x - 1.0f, title.y - 1.0f, w.rect.width + 2.0f,
                        w.rect.height + theme::TITLE_H + 2.0f};

        DrawRectangleRec({frame.x + 6.0f, frame.y + 8.0f, frame.width,
                          frame.height},
                         Color{0, 0, 0, 60});
        DrawRectangleRec(frame, theme::WIN_BORDER);
        DrawRectangleRec(title, active ? theme::TITLE_ACTIVE : theme::TITLE_IDLE);
        DrawRectangleRec(w.rect, theme::WIN_BODY);

        // title bar content
        DrawRectangleRounded({title.x + 7.0f, title.y + 7.0f, 14.0f, 14.0f}, 0.25f,
                             4, app->Accent());
        theme::Text(theme::UI(), app->Title(), title.x + 29.0f, title.y + 7.0f,
                    14.0f, theme::TITLE_TEXT);

        ui::SetEnabled(active || true);  // chrome always clickable
        Rectangle closeB{title.x + title.width - 28.0f, title.y + 5.0f, 22.0f, 18.0f};
        Rectangle minB{title.x + title.width - 54.0f, title.y + 5.0f, 22.0f, 18.0f};
        if (ui::TinyButton(minB, "_")) w.minimized = true;
        if (ui::TinyButton(closeB, "X")) w.open = false;

        // content
        ui::SetEnabled(active);
        BeginScissorMode((int)w.rect.x, (int)w.rect.y, (int)w.rect.width,
                         (int)w.rect.height);
        app->Draw(session_, w.rect, active);
        EndScissorMode();

        // resize grip
        Vector2 g{w.rect.x + w.rect.width - 4.0f, w.rect.y + w.rect.height - 4.0f};
        for (int i = 0; i < 3; ++i)
            DrawLineEx({g.x - 4.0f * i - 4.0f, g.y},
                       {g.x, g.y - 4.0f * i - 4.0f}, 1.0f,
                       Color{150, 160, 172, 255});
    }
    ui::SetEnabled(true);
}

// ---------------------------------------------------------------- taskbar

void Desktop::DrawTaskbar() {
    float h = theme::TASKBAR_H;
    Rectangle bar{0.0f, GetScreenHeight() - h, (float)GetScreenWidth(), h};
    DrawRectangleRec(bar, theme::TASKBAR);
    DrawLineEx({bar.x, bar.y}, {bar.x + bar.width, bar.y}, 1.0f,
               theme::TASKBAR_EDGE);

    ui::SetEnabled(true);
    Rectangle start{6.0f, bar.y + 5.0f, 108.0f, h - 10.0f};
    bool hov = ui::Hover(start);
    DrawRectangleRounded(start, 0.2f, 6,
                         startOpen_ ? theme::ACCENT_DARK
                                    : hov ? Color{44, 58, 74, 255}
                                          : Color{34, 46, 60, 255});
    theme::Text(theme::UI(), brand::OS_NAME, start.x + 12.0f, start.y + 7.0f,
                14.0f, Color{226, 236, 246, 255});
    if (ui::Clicked(start)) startOpen_ = !startOpen_;

    float x = start.x + start.width + 10.0f;
    for (size_t i = 0; i < wins_.size(); ++i) {
        if (!wins_[i].open) continue;
        int top = order_.empty() ? -1 : order_.back();
        bool activeWin = ((int)i == top) && !wins_[i].minimized;
        std::string cap = apps_[i]->Title();
        size_t dash = cap.find(" - ");
        if (dash != std::string::npos) cap = cap.substr(0, dash);

        Rectangle b{x, bar.y + 5.0f, 158.0f, h - 10.0f};
        if (b.x + b.width > bar.width - 200.0f) break;
        bool hovered = ui::Hover(b);
        DrawRectangleRounded(b, 0.18f, 6,
                             activeWin ? Color{50, 68, 88, 255}
                                       : hovered ? Color{40, 54, 70, 255}
                                                 : Color{30, 40, 52, 255});
        DrawRectangleRec({b.x, b.y + b.height - 3.0f, b.width, 3.0f},
                         apps_[i]->Accent());
        BeginScissorMode((int)b.x, (int)b.y, (int)b.width - 8, (int)b.height);
        theme::Text(theme::UI(), cap, b.x + 10.0f, b.y + 7.0f, 13.0f,
                    Color{216, 228, 240, 255});
        EndScissorMode();
        if (ui::Clicked(b)) {
            if (activeWin) {
                wins_[i].minimized = true;
            } else {
                wins_[i].minimized = false;
                Raise((int)i);
            }
        }
        x += b.width + 6.0f;
    }

    // right side: connection + case + clock
    float rx = bar.width - 12.0f;
    std::string clk = Clock12();
    float cw = theme::TextW(theme::UI(), clk, 14.0f);
    theme::Text(theme::UI(), clk, rx - cw, bar.y + 5.0f, 14.0f,
                Color{226, 236, 246, 255});
    std::string dt = DateShort();
    float dw = theme::TextW(theme::UI(), dt, 10.0f);
    theme::Text(theme::UI(), dt, rx - dw, bar.y + 22.0f, 10.0f,
                Color{140, 164, 188, 255});
    rx -= std::max(cw, dw) + 18.0f;

    std::string caseTxt = session_.hasCase() ? "CASE #" + session_.caseCode()
                                             : "NO CASE";
    float ctw = theme::TextW(theme::Mono(), caseTxt, 12.0f);
    theme::Text(theme::Mono(), caseTxt, rx - ctw, bar.y + 13.0f, 12.0f,
                session_.hasCase() ? Color{180, 210, 236, 255}
                                   : Color{120, 140, 160, 255});
    rx -= ctw + 18.0f;

    Color dot = session_.online ? theme::OK : theme::DANGER;
    DrawCircleV({rx - 6.0f, bar.y + h * 0.5f}, 5.0f, dot);
    std::string net = session_.online ? "connected" : "offline";
    float nw = theme::TextW(theme::UI(), net, 11.0f);
    theme::Text(theme::UI(), net, rx - 16.0f - nw, bar.y + 14.0f, 11.0f,
                Color{150, 172, 194, 255});
}

// ------------------------------------------------------------- start menu

void Desktop::DrawStartMenu() {
    float h = 60.0f + apps_.size() * 30.0f + 96.0f;
    Rectangle menu{6.0f, GetScreenHeight() - theme::TASKBAR_H - h, 280.0f, h};
    DrawRectangleRec({menu.x + 5.0f, menu.y + 5.0f, menu.width, menu.height},
                     Color{0, 0, 0, 70});
    DrawRectangleRec(menu, Color{32, 42, 54, 250});
    DrawRectangleLinesEx(menu, 1.0f, theme::TASKBAR_EDGE);
    DrawRectangleRec({menu.x, menu.y, menu.width, 44.0f}, theme::ACCENT_DARK);
    theme::Text(theme::UI(), std::string(brand::OS_NAME) + " " + brand::OS_VERSION,
                menu.x + 14.0f, menu.y + 8.0f, 16.0f, theme::TITLE_TEXT);
    theme::Text(theme::UI(), session_.playerName, menu.x + 14.0f, menu.y + 26.0f,
                11.0f, Color{170, 200, 226, 255});

    float y = menu.y + 52.0f;
    ui::SetEnabled(true);
    for (size_t i = 0; i < apps_.size(); ++i) {
        Rectangle item{menu.x + 6.0f, y, menu.width - 12.0f, 28.0f};
        bool hov = ui::Hover(item);
        if (hov) DrawRectangleRec(item, Color{58, 78, 98, 255});
        DrawRectangleRec({item.x + 6.0f, item.y + 9.0f, 10.0f, 10.0f},
                         apps_[i]->Accent());
        theme::Text(theme::UI(), apps_[i]->Title(), item.x + 24.0f, item.y + 7.0f,
                    13.0f, Color{220, 232, 244, 255});
        if (ui::Clicked(item)) {
            OpenApp(apps_[i]->Id(), "");
            startOpen_ = false;
        }
        y += 30.0f;
    }

    ui::Divider(menu.x + 10.0f, y + 6.0f, menu.width - 20.0f);
    y += 14.0f;
    if (ui::Button({menu.x + 10.0f, y, menu.width - 20.0f, 28.0f},
                   "FIELD MANUAL  (F1)")) {
        helpOpen_ = true;
        startOpen_ = false;
    }
    y += 34.0f;
    if (ui::Button({menu.x + 10.0f, y, menu.width - 20.0f, 28.0f},
                   "SHUT DOWN")) {
        quit_ = true;
    }
}

// ----------------------------------------------------------------- toasts

void Desktop::DrawToasts() {
    float y = GetScreenHeight() - theme::TASKBAR_H - 16.0f;
    for (auto it = session_.toasts().rbegin(); it != session_.toasts().rend(); ++it) {
        const Toast& t = *it;
        float w = std::min(430.0f, theme::TextW(theme::UI(), t.text, 13.0f) + 34.0f);
        float th = theme::TextWrapped(theme::UI(), t.text, {0, 0, w - 28.0f, 999},
                                      13.0f, theme::TEXT, false);
        float boxH = th + 20.0f;
        y -= boxH + 8.0f;
        Rectangle box{GetScreenWidth() - w - 16.0f, y, w, boxH};
        unsigned char alpha = (unsigned char)(std::min(1.0f, t.ttl / 0.6f) * 244);
        DrawRectangleRec(box, Color{244, 246, 250, alpha});
        DrawRectangleRec({box.x, box.y, 4.0f, box.height},
                         t.error ? theme::DANGER : theme::ACCENT);
        theme::TextWrapped(theme::UI(), t.text,
                           {box.x + 14.0f, box.y + 10.0f, w - 28.0f, th + 2},
                           13.0f, theme::TEXT);
    }
}

// ------------------------------------------------------------------- help

void Desktop::DrawHelp() {
    DrawRectangleRec({0, 0, (float)GetScreenWidth(), (float)GetScreenHeight()},
                     Color{0, 0, 0, 150});
    Rectangle card{GetScreenWidth() * 0.5f - 330.0f,
                   GetScreenHeight() * 0.5f - 250.0f, 660.0f, 500.0f};
    DrawRectangleRec(card, theme::WIN_PANEL);
    DrawRectangleLinesEx(card, 1.0f, theme::WIN_BORDER);
    DrawRectangleRec({card.x, card.y, card.width, 40.0f}, theme::TITLE_ACTIVE);
    theme::Text(theme::UI(), "Field Manual", card.x + 16.0f, card.y + 11.0f,
                16.0f, theme::TITLE_TEXT);

    const char* body =
        "You are an analyst in the incident response unit. A case arrives with "
        "one usable clue: a link the victim clicked. Everything else you have to "
        "earn.\n\n"
        "THE CHAIN\n"
        "    domain -> address -> co-hosted domains -> malware -> campaign -> actor\n\n"
        "Each application picks up where the previous one leaves off:\n\n"
        "  CaseDesk      the incident queue, hints, and the final resolution\n"
        "  IntelSearch   resolve a domain or address, see what else is hosted there\n"
        "  MalwareDB     a malware family's campaigns and infrastructure\n"
        "  Web Search    published reporting -- this is where attribution comes from\n"
        "  Directory     threat actor profiles and civilian records\n"
        "  Evidence Map  every relationship you have uncovered, drawn as a graph\n"
        "  Case Report   name the actor, campaign, domain and malware\n\n"
        "WHAT MAKES IT HARD\n"
        "Not everything you find belongs to your case. Shared hosting means "
        "unrelated domains sit on the same address, and decoy chains are built "
        "to look exactly like the real one. The chain that counts is the one "
        "rooted in the domain from the victim's own statement.\n\n"
        "SCORING\n"
        "Hints and returned reports cost points. Pinned evidence that supports "
        "the case adds points; pinned noise subtracts. A wrong report can always "
        "be resubmitted.\n\n"
        "F1 toggles this manual.  ESC closes overlays.";

    theme::TextWrapped(theme::Mono(), body,
                       {card.x + 22.0f, card.y + 56.0f, card.width - 44.0f,
                        card.height - 112.0f},
                       12.5f, theme::TEXT);

    ui::SetEnabled(true);
    if (ui::Button({card.x + card.width - 112.0f, card.y + card.height - 42.0f,
                    96.0f, 30.0f},
                   "CLOSE")) {
        helpOpen_ = false;
    }
}
