#pragma once
#include <raylib.h>

#include <memory>
#include <string>
#include <vector>

#include "../apps/app.h"
#include "../core/session.h"

// The fake operating system. Owns one instance of every application, the
// window stack, the taskbar and the desktop icons.
class Desktop {
  public:
    Desktop();

    void Update(float dt);
    void Draw();

    bool wantsQuit() const { return quit_; }
    Session& session() { return session_; }

  private:
    struct Win {
        int appIndex = 0;
        Rectangle rect{0, 0, 0, 0};
        bool open = false;
        bool minimized = false;
        bool dragging = false;
        bool resizing = false;
        Vector2 grab{0, 0};
    };

    void OpenApp(const std::string& id, const std::string& query);
    int FindApp(const std::string& id) const;
    void Raise(int winIndex);
    int TopWindowAt(Vector2 p) const;

    void DrawWallpaper();
    void DrawIcons();
    void DrawWindows();
    void DrawTaskbar();
    void DrawStartMenu();
    void DrawToasts();
    void DrawHelp();
    void DrawBoot();

    Session session_;
    std::vector<std::unique_ptr<App>> apps_;
    std::vector<Win> wins_;
    std::vector<int> order_;   // back to front

    bool startOpen_ = false;
    bool helpOpen_ = false;
    bool quit_ = false;
    float boot_ = 0.0f;
    float healthTimer_ = 0.0f;
    int iconSelected_ = -1;
};
