// The four query tools. They share a base class because they differ only in
// which endpoint they hit and what they tell the player to type.
#include <algorithm>
#include <vector>

#include "../core/theme.h"
#include "../ui/widgets.h"
#include "common.h"
#include "factories.h"

namespace {

class LookupApp : public App {
  public:
    LookupApp(std::string id, std::string title, std::string glyph, Color accent,
              std::string path, std::string placeholder, std::string blurb)
        : id_(std::move(id)),
          title_(std::move(title)),
          glyph_(std::move(glyph)),
          accent_(accent),
          path_(std::move(path)),
          placeholder_(std::move(placeholder)),
          blurb_(std::move(blurb)) {}

    std::string Id() const override { return id_; }
    std::string Title() const override { return title_; }
    std::string Glyph() const override { return glyph_; }
    Color Accent() const override { return accent_; }

    void OnOpen(Session& s, const std::string& query) override {
        if (query.empty()) return;
        finder_.field.text = query;
        history_.clear();
        finder_.Search(s, path_, query);
    }

    void Draw(Session& s, Rectangle c, bool active) override {
        finder_.Poll(s);
        (void)active;

        // ---- query bar
        Rectangle bar{c.x, c.y, c.width, 54.0f};
        DrawRectangleRec(bar, Color{238, 241, 246, 255});
        DrawLineEx({bar.x, bar.y + bar.height}, {bar.x + bar.width, bar.y + bar.height},
                   1.0f, Color{210, 216, 224, 255});

        bool back = !history_.empty();
        float bx = bar.x + theme::PAD;
        if (back) {
            if (ui::Button({bx, bar.y + 13.0f, 70.0f, 28.0f}, "< BACK")) {
                finder_.result = history_.back();
                history_.pop_back();
                finder_.scroll.y = 0.0f;
            }
            bx += 78.0f;
        }
        Rectangle field{bx, bar.y + 13.0f, c.width - (bx - bar.x) - 200.0f, 28.0f};
        bool enter = ui::TextFieldW(finder_.field, field, placeholder_);
        Rectangle go{field.x + field.width + 8.0f, bar.y + 13.0f, 90.0f, 28.0f};
        bool clicked = ui::Button(go, "SEARCH", s.hasCase() && !finder_.busy());
        Rectangle clr{go.x + 98.0f, bar.y + 13.0f, 74.0f, 28.0f};
        if (ui::Button(clr, "CLEAR")) {
            finder_.field.text.clear();
            finder_.Reset();
            history_.clear();
        }

        if ((enter || clicked) && s.hasCase()) {
            history_.clear();
            finder_.Search(s, path_, finder_.field.text);
        }

        // ---- body
        Rectangle body{c.x, c.y + 54.0f, c.width, c.height - 54.0f};
        DrawRectangleRec(body, theme::WIN_BODY);
        Rectangle inner{body.x + theme::PAD, body.y + theme::PAD,
                        body.width - theme::PAD * 2.0f,
                        body.height - theme::PAD * 2.0f};

        if (!s.hasCase()) {
            theme::TextWrapped(theme::UI(),
                               "No case is open. Open CaseDesk and request a "
                               "case file before querying the indexes.",
                               inner, 14.0f, theme::TEXT_DIM);
            return;
        }

        if (finder_.busy()) {
            ui::Spinner({inner.x + inner.width * 0.5f, inner.y + 80.0f}, 16.0f,
                        theme::ACCENT);
            std::string msg = "Querying index for \"" + finder_.pendingQuery + "\"";
            float w = theme::TextW(theme::UI(), msg, 13.0f);
            theme::Text(theme::UI(), msg, inner.x + (inner.width - w) * 0.5f,
                        inner.y + 112.0f, 13.0f, theme::TEXT_DIM);
            return;
        }

        rec::Action action;
        ui::BeginScroll(finder_.scroll, inner);
        float y = inner.y - finder_.scroll.y;

        if (!finder_.error.empty()) {
            y = rec::Empty(finder_.error, inner, y);
        } else if (finder_.result.is_object() && finder_.result.contains("kind")) {
            y = DrawSingle(s, inner, y, action);
        } else if (finder_.result.is_object() && finder_.result.contains("query")) {
            if (!jbool(finder_.result, "found")) {
                y = rec::Empty(jstr(finder_.result, "message", "No results."),
                               inner, y);
            } else {
                y = rec::Envelope(s, finder_.result, inner, y, action);
            }
        } else {
            y += theme::TextWrapped(theme::UI(), blurb_,
                                    {inner.x, y, inner.width - 20.0f, 400.0f},
                                    14.0f, theme::TEXT_DIM);
        }
        ui::EndScroll(finder_.scroll, inner, y - (inner.y - finder_.scroll.y));

        if (action.kind == rec::Action::FetchUrl) {
            history_.push_back(finder_.result);
            finder_.Fetch(s, action.url);
        } else {
            rec::Apply(s, action);
        }
    }

  private:
    float DrawSingle(Session& s, Rectangle inner, float y, rec::Action& a) {
        const std::string kind = jstr(finder_.result, "kind");
        if (kind == "domain") return rec::Domain(s, finder_.result, inner, y, a);
        if (kind == "ip") return rec::Ip(s, finder_.result, inner, y, a);
        if (kind == "malware") return rec::Malware(s, finder_.result, inner, y, a);
        if (kind == "campaign") return rec::Campaign(s, finder_.result, inner, y, a);
        if (kind == "actor") return rec::Actor(s, finder_.result, inner, y, a);
        if (kind == "person") return rec::Person(s, finder_.result, inner, y, a);
        return y;
    }

    std::string id_, title_, glyph_;
    Color accent_;
    std::string path_, placeholder_, blurb_;
    rec::Finder finder_;
    std::vector<json> history_;
};

}  // namespace

std::unique_ptr<App> MakeIntelSearch() {
    return std::make_unique<LookupApp>(
        "intelsearch", "IntelSearch - Threat Intelligence", "IS",
        theme::ACCENT, "/api/intel", "domain, URL or IP address",
        "IntelSearch queries the threat-intelligence index.\n\n"
        "Paste the link from the victim's statement. A malicious domain will "
        "usually resolve to an address, and that address will usually be "
        "hosting more than one thing.\n\n"
        "Accepted input:\n"
        "    secure-account-check.example\n"
        "    https://secure-account-check.example/login\n"
        "    203.0.113.42\n\n"
        "Remember that co-hosting is not attribution. Other domains on the "
        "same address may have nothing to do with this incident.");
}

std::unique_ptr<App> MakeMalwareDb() {
    return std::make_unique<LookupApp>(
        "malwaredb", "MalwareDB - Family Index", "MW", theme::DANGER,
        "/api/malware", "malware family name",
        "MalwareDB indexes malware families, the campaigns they have been "
        "seen in, and the infrastructure they beacon to.\n\n"
        "Search a family name you recovered from IntelSearch. Families are "
        "shared between unrelated crews, so prefer the one that was actually "
        "staged on the domain your victim visited.");
}

std::unique_ptr<App> MakeDirectory() {
    return std::make_unique<LookupApp>(
        "directory", "Directory - People and Aliases", "DIR", theme::NOISE,
        "/api/directory", "alias, name, email or username",
        "Directory is a people-search index. It holds two very different kinds "
        "of record in one place:\n\n"
        "    - threat actor aliases, with their tracked campaigns and "
        "infrastructure\n"
        "    - civilian records, including breach exposure\n\n"
        "Search an alias you picked up from published reporting, or look up "
        "the reporting party from your case file.");
}

std::unique_ptr<App> MakeWebSearch() {
    return std::make_unique<LookupApp>(
        "websearch", "Web Search", "WS", theme::OK, "/api/websearch",
        "campaign name, malware family or alias",
        "A search over public security writing: blogs, community reports, "
        "and researcher notes.\n\n"
        "This is where attribution comes from. Infrastructure tells you what "
        "happened; published reporting tells you who somebody thinks did it.\n\n"
        "Try a campaign name. Read carefully -- not every article names an "
        "actor, and some of them are about entirely different activity.");
}
