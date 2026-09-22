#pragma once
#include <raylib.h>

#include <string>

#include "../core/session.h"
#include "../ui/widgets.h"

namespace rec {

// What a record's buttons asked for. Renderers never mutate the session
// directly -- they report an action and the owning app applies it.
struct Action {
    enum Kind {
        None,
        Pin,
        OpenApp,   // app + query
        FetchUrl,  // absolute url, replaces the app's current result
        OpenGraph
    } kind = None;

    std::string app;
    std::string query;
    std::string url;
    std::string entityKind;
    long long entityId = 0;
    std::string label;
};

void Apply(Session& s, const Action& a);

// One search box + one in-flight request + one result document.
struct Finder {
    ui::TextField field;
    ui::Scroll scroll;
    net::Async req;
    json result = json::object();
    std::string error;
    std::string pendingQuery;

    void Search(Session& s, const std::string& path, const std::string& q);
    void Fetch(Session& s, const std::string& url);
    void Poll(Session& s);
    bool busy() const { return req.pending(); }
    void Reset();
};

// Each returns the y coordinate just below what it drew.
float Header(const std::string& kind, const std::string& title,
             const std::string& status, Rectangle box, float y);

float Domain(Session& s, const json& d, Rectangle box, float y, Action& a);
float Ip(Session& s, const json& d, Rectangle box, float y, Action& a);
float Malware(Session& s, const json& d, Rectangle box, float y, Action& a);
float Campaign(Session& s, const json& d, Rectangle box, float y, Action& a);
float Actor(Session& s, const json& d, Rectangle box, float y, Action& a);
float Person(Session& s, const json& d, Rectangle box, float y, Action& a);
float Article(Session& s, const json& d, Rectangle box, float y, Action& a);

// Renders a whole SearchResponse envelope in a fixed order.
float Envelope(Session& s, const json& env, Rectangle box, float y, Action& a);

// Standard "nothing found" panel.
float Empty(const std::string& message, Rectangle box, float y);

// The [ADD TO EVIDENCE] control, greyed out once pinned.
float PinButton(Session& s, const std::string& kind, long long id,
                const std::string& label, Rectangle box, float y, Action& a,
                bool withGraphButton = true);

}  // namespace rec
