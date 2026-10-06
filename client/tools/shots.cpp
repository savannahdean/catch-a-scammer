// Screenshot harness: drives the real app windows against a running API and
// saves what they draw, so changes can be checked without clicking through
// the game by hand. Not part of the game build.
//
//   build:  see client/Makefile target `shots`
//   run:    ./build/shots.exe <out_dir> <difficulty> <scenario> [api]
//
// It opens a case, renders CaseDesk with the exhibits, then follows the first
// pivot each exhibit offers into every tool it names, rendering each window.
// Finally it renders the Case Report form and the Evidence Map.
#include <raylib.h>

#include <chrono>
#include <cstdio>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include "../src/apps/app.h"
#include "../src/core/session.h"
#include "../src/core/theme.h"
#include "../src/net/http.h"
#include "../src/os/desktop.h"
#include "../src/ui/widgets.h"

namespace {

const int W = 1000, H = 1000;

void Frames(Session& s, App& app, int n) {
    for (int i = 0; i < n; ++i) {
        s.Update(1.0f / 60.0f);
        OpenRequest ignored;
        while (s.popOpenRequest(ignored)) {
        }
        BeginDrawing();
        ClearBackground(theme::WIN_BODY);
        ui::SetEnabled(false);   // nobody is clicking
        app.Draw(s, Rectangle{0, 0, (float)W, (float)H}, true);
        ui::FlushPopups();
        EndDrawing();
        std::this_thread::sleep_for(std::chrono::milliseconds(15));
    }
}

void Shot(Session& s, App& app, const std::string& path) {
    Frames(s, app, 90);   // let requests finish and the layout settle
    TakeScreenshot(path.c_str());
    std::printf("  saved %s\n", path.c_str());
}

// every (app, query) an "open" row offers, in order
void Harvest(const json& j, std::vector<std::pair<std::string, std::string>>& out) {
    if (j.is_object()) {
        if (j.contains("open") && j["open"].is_object())
            out.push_back({jstr(j["open"], "app"), jstr(j["open"], "query")});
        for (auto it = j.begin(); it != j.end(); ++it) Harvest(*it, out);
    } else if (j.is_array()) {
        for (const auto& x : j) Harvest(x, out);
    }
}

const std::map<std::string, std::string> ROUTE = {
    {"intelsearch", "/api/intel"},   {"malwaredb", "/api/malware"},
    {"websearch", "/api/websearch"}, {"directory", "/api/directory"},
    {"social", "/api/social"},       {"reverseimage", "/api/reverseimage"},
    {"phone", "/api/phone"},         {"sms", "/api/sms"},
    {"doclab", "/api/documents"},    {"audiolab", "/api/audio"},
    {"payments", "/api/payments"},   {"moneytrail", "/api/moneytrail"},
    {"complaints", "/api/complaints"}, {"dns", "/api/dns"},
    {"whois", "/api/whois"},         {"certs", "/api/certs"},
    {"urlscan", "/api/urlscan"},     {"breach", "/api/breach"}};

}  // namespace

int main(int argc, char** argv) {
    if (argc < 4) {
        std::printf("usage: shots <out_dir> <difficulty> <scenario> [api]\n");
        return 2;
    }
    std::string out = argv[1], diff = argv[2], scenario = argv[3];

    net::GlobalInit();
    SetTraceLogLevel(LOG_WARNING);
    SetConfigFlags(FLAG_WINDOW_HIDDEN);
    InitWindow(W, H, "shots");
    theme::LoadFonts();
    {
        Session s;
        if (argc > 4) s.apiBase = argv[4];
        std::vector<std::unique_ptr<App>> apps = MakeApps();
        std::map<std::string, App*> byId;
        for (auto& a : apps) byId[a->Id()] = a.get();

        s.startNewCase(diff, scenario);
        for (int i = 0; i < 600 && !s.hasCase(); ++i) {
            s.Update(0.016f);
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        if (!s.hasCase()) {
            std::printf("no case\n");
            return 1;
        }
        std::printf("case %s (%s, %s)\n", s.caseCode().c_str(), diff.c_str(), scenario.c_str());

        App& desk = *byId["casedesk"];
        desk.OnOpen(s, "");
        Shot(s, desk, out + "/01_casedesk.png");

        // follow the exhibits' pivots: one window per tool they point at
        net::Response ex = net::Get(s.url("/api/cases/" + std::to_string(s.caseId) + "/exhibits"));
        std::vector<std::pair<std::string, std::string>> leads;
        Harvest(json::parse(ex.body), leads);
        std::set<std::string> done;
        int n = 2;
        for (size_t i = 0; i < leads.size() && n < 14; ++i) {
            auto [app, q] = leads[i];
            if (done.count(app) || !byId.count(app)) continue;
            done.insert(app);
            // pivots inside each result become further leads
            if (ROUTE.count(app)) {
                net::Response r = net::Get(s.url(ROUTE.at(app), s.caseParams({{"q", q}})));
                if (r.ok()) Harvest(json::parse(r.body), leads);
            }
            byId[app]->OnOpen(s, q);
            char name[64];
            std::snprintf(name, sizeof(name), "/%02d_%s.png", n++, app.c_str());
            Shot(s, *byId[app], out + name);
        }

        App& report = *byId["casereport"];
        report.OnOpen(s, "");
        Shot(s, report, out + "/90_casereport.png");
    }
    {
        // the whole shell: icons, a couple of windows, the taskbar
        Desktop d;
        if (argc > 4) d.session().apiBase = argv[4];
        auto frames = [&](int n) {
            for (int i = 0; i < n; ++i) {
                d.Update(1.0f / 60.0f);
                BeginDrawing();
                d.Draw();
                EndDrawing();
                std::this_thread::sleep_for(std::chrono::milliseconds(15));
            }
        };
        frames(200);   // boot sequence
        d.session().startNewCase(diff, scenario);
        frames(150);
        d.session().requestOpen("casedesk");
        frames(120);
        TakeScreenshot((out + "/95_desktop.png").c_str());
        std::printf("  saved %s/95_desktop.png\n", out.c_str());
    }
    theme::UnloadFonts();
    CloseWindow();
    net::GlobalShutdown();
    return 0;
}
