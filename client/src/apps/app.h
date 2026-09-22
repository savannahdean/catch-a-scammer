#pragma once
#include <raylib.h>

#include <memory>
#include <string>
#include <vector>

#include "../core/session.h"

// Every window in the fake OS is one of these. The shell owns exactly one
// instance of each, so state (search text, scroll position, last result)
// survives minimising and reopening -- like a real desktop application.
class App {
  public:
    virtual ~App() = default;

    virtual std::string Id() const = 0;       // "intelsearch"
    virtual std::string Title() const = 0;    // window + taskbar caption
    virtual std::string Glyph() const = 0;    // 2-3 chars on the desktop icon
    virtual Color Accent() const = 0;

    virtual Vector2 DefaultSize() const { return Vector2{860.0f, 580.0f}; }
    virtual bool RequiresCase() const { return true; }

    // Called when the shell opens/raises the window, optionally with a query
    // handed over from another app.
    virtual void OnOpen(Session& s, const std::string& query) {
        (void)s;
        (void)query;
    }

    // Draw and handle input inside the window's content rectangle.
    virtual void Draw(Session& s, Rectangle content, bool active) = 0;
};

std::vector<std::unique_ptr<App>> MakeApps();
