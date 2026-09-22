#include "common.h"

#include <algorithm>

#include "../core/theme.h"

namespace rec {
namespace {

constexpr float FS = 14.0f;
constexpr float KEY_W = 140.0f;

std::string Or(const std::string& v, const char* fallback) {
    return v.empty() ? fallback : v;
}

float Field(const std::string& k, const std::string& v, Rectangle box, float y,
            Color c = theme::TEXT) {
    ui::KeyValue(k, v, box.x, y, KEY_W, c);
    return y + 20.0f;
}

}  // namespace

void Apply(Session& s, const Action& a) {
    switch (a.kind) {
        case Action::Pin:
            s.pinEvidence(a.entityKind, a.entityId, a.label);
            break;
        case Action::OpenApp:
            s.requestOpen(a.app, a.query);
            break;
        case Action::OpenGraph:
            s.requestOpen("evidencemap");
            break;
        default:
            break;
    }
}

void Finder::Reset() {
    result = json::object();
    error.clear();
    scroll.y = 0.0f;
}

void Finder::Search(Session& s, const std::string& path, const std::string& q) {
    if (req.pending() || !s.hasCase()) return;
    std::string trimmed = q;
    while (!trimmed.empty() && trimmed.front() == ' ') trimmed.erase(trimmed.begin());
    while (!trimmed.empty() && trimmed.back() == ' ') trimmed.pop_back();
    if (trimmed.empty()) return;
    pendingQuery = trimmed;
    std::string u = s.url(path, s.caseParams({{"q", trimmed}}));
    error.clear();
    req.start([u]() { return net::Get(u); });
}

void Finder::Fetch(Session& s, const std::string& u) {
    if (req.pending()) return;
    (void)s;
    error.clear();
    req.start([u]() { return net::Get(u); });
}

void Finder::Poll(Session& s) {
    if (!req.ready()) return;
    net::Response r = req.take();
    if (r.ok()) {
        try {
            result = json::parse(r.body);
            scroll.y = 0.0f;
            error.clear();
        } catch (const std::exception& e) {
            error = std::string("Could not decode the response: ") + e.what();
        }
    } else if (r.status == 404) {
        result = json::object();
        error = "NO RECORDS FOUND.\n\nThat identifier is not indexed for this "
                "case. Take the term from a record you already hold.";
    } else {
        result = json::object();
        error = r.error.empty()
                    ? "Service error (HTTP " + std::to_string(r.status) + ")."
                    : "Service unreachable: " + r.error;
        s.online = false;
    }
}

float Header(const std::string& kind, const std::string& title,
             const std::string& status, Rectangle box, float y) {
    Rectangle bar{box.x, y, box.width, 40.0f};
    DrawRectangleRec(bar, Color{242, 245, 249, 255});
    DrawRectangleRec({bar.x, bar.y, 4.0f, bar.height}, theme::ACCENT);
    theme::Text(theme::UI(), kind, bar.x + 14.0f, bar.y + 5.0f, 11.0f,
                theme::TEXT_DIM);
    theme::Text(theme::Mono(), title, bar.x + 14.0f, bar.y + 18.0f, 16.0f,
                theme::TEXT);
    if (!status.empty()) {
        std::string up = status;
        std::transform(up.begin(), up.end(), up.begin(), ::toupper);
        float w = theme::TextW(theme::UI(), up, 12.0f) + 18.0f;
        ui::Badge({bar.x + bar.width - w - 12.0f, bar.y + 11.0f, w, 18.0f}, up,
                  theme::StatusColor(status));
    }
    return y + 48.0f;
}

float PinButton(Session& s, const std::string& kind, long long id,
                const std::string& label, Rectangle box, float y, Action& a,
                bool withGraphButton) {
    bool pinned = s.isPinned(kind, id);
    Rectangle b1{box.x, y, 170.0f, 26.0f};
    if (ui::Button(b1, pinned ? "IN EVIDENCE" : "ADD TO EVIDENCE", !pinned)) {
        a.kind = Action::Pin;
        a.entityKind = kind;
        a.entityId = id;
        a.label = label;
    }
    if (withGraphButton) {
        Rectangle b2{box.x + 180.0f, y, 130.0f, 26.0f};
        if (ui::Button(b2, "OPEN GRAPH")) a.kind = Action::OpenGraph;
    }
    return y + 36.0f;
}

// ---------------------------------------------------------------- domain

float Domain(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("DOMAIN", jstr(d, "domain_name"), jstr(d, "status"), box, y);
    y = Field("First seen", Or(jstr(d, "first_seen"), "unknown"), box, y);
    y = Field("Last seen", Or(jstr(d, "last_seen"), "unknown"), box, y);
    y = Field("Registrar", Or(jstr(d, "registrar"), "unknown"), box, y);
    y += 8.0f;

    if (d.contains("associated_ips") && d["associated_ips"].is_array() &&
        !d["associated_ips"].empty()) {
        ui::SectionLabel("ASSOCIATED ADDRESSES", box.x, y);
        y += 24.0f;
        for (const auto& ip : d["associated_ips"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(ip, "ip_address"), "VIEW IP >", false,
                        theme::ACCENT)) {
                a.kind = Action::FetchUrl;
                a.url = s.url("/api/intel/ip/" + std::to_string(jint(ip, "ip_id")),
                              s.caseParams());
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    if (d.contains("delivers_malware") && d["delivers_malware"].is_array() &&
        !d["delivers_malware"].empty()) {
        ui::SectionLabel("STAGED PAYLOADS", box.x, y);
        y += 24.0f;
        for (const auto& mw : d["delivers_malware"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(mw, "family_name"), "VIEW MALWARE >", false,
                        theme::DANGER)) {
                a.kind = Action::OpenApp;
                a.app = "malwaredb";
                a.query = jstr(mw, "family_name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    return PinButton(s, "domain", jint(d, "domain_id"), jstr(d, "domain_name"),
                     box, y, a);
}

// -------------------------------------------------------------------- ip

float Ip(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("IP ADDRESS", jstr(d, "ip_address"), jstr(d, "status"), box, y);

    ui::SectionLabel("APPROXIMATE LOCATION", box.x, y);
    y += 24.0f;
    y = Field("Country", Or(jstr(d, "country"), "unknown"), box, y);
    y = Field("Region", Or(jstr(d, "region"), "unknown"), box, y);
    y = Field("City", Or(jstr(d, "city"), "unknown"), box, y);
    if (d.contains("latitude") && !d["latitude"].is_null()) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%.4f, %.4f",
                 d["latitude"].get<double>(), d["longitude"].get<double>());
        y = Field("Coordinates", buf, box, y);
    }
    y += 10.0f;

    ui::SectionLabel("NETWORK INFORMATION", box.x, y);
    y += 24.0f;
    y = Field("ASN", Or(jstr(d, "asn"), "unknown"), box, y);
    y = Field("Organization", Or(jstr(d, "provider_name"), "unknown"), box, y);
    std::string rep = Or(jstr(d, "provider_reputation"), "unknown");
    Color repC = rep == "bulletproof" ? theme::DANGER
                 : rep == "mixed"     ? theme::WARN
                 : rep == "clean"     ? theme::OK
                                      : theme::TEXT_DIM;
    y = Field("Reputation", rep, box, y, repC);
    y = Field("Abuse contact", Or(jstr(d, "abuse_email"), "none published"), box, y);
    y += 10.0f;

    if (d.contains("related_domains") && d["related_domains"].is_array() &&
        !d["related_domains"].empty()) {
        ui::SectionLabel("DOMAINS ON THIS ADDRESS", box.x, y);
        y += 20.0f;
        theme::Text(theme::UI(),
                    "Co-hosting is common. Shared address != shared operator.",
                    box.x, y, 12.0f, theme::TEXT_DIM);
        y += 20.0f;
        for (const auto& dm : d["related_domains"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            std::string right = jstr(dm, "first_seen", "?");
            if (ui::Row(row, jstr(dm, "domain_name"), right, false,
                        theme::StatusColor(jstr(dm, "status")))) {
                a.kind = Action::FetchUrl;
                a.url = s.url(
                    "/api/intel/domain/" + std::to_string(jint(dm, "domain_id")),
                    s.caseParams());
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    if (d.contains("related_malware") && d["related_malware"].is_array() &&
        !d["related_malware"].empty()) {
        ui::SectionLabel("MALWARE BEACONING HERE", box.x, y);
        y += 24.0f;
        for (const auto& mw : d["related_malware"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(mw, "family_name"), "VIEW MALWARE >", false,
                        theme::DANGER)) {
                a.kind = Action::OpenApp;
                a.app = "malwaredb";
                a.query = jstr(mw, "family_name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    return PinButton(s, "ip", jint(d, "ip_id"), jstr(d, "ip_address"), box, y, a);
}

// --------------------------------------------------------------- malware

float Malware(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("MALWARE FAMILY", jstr(d, "family_name"), "", box, y);
    y = Field("Type", jstr(d, "malware_type"), box, y);
    y = Field("First observed", Or(jstr(d, "first_observed"), "unknown"), box, y);
    y = Field("Source", Or(jstr(d, "source"), "community"), box, y);
    std::string h = jstr(d, "sha256");
    if (!h.empty()) y = Field("SHA256", h.substr(0, 32) + "...", box, y);
    y += 10.0f;

    if (d.contains("campaigns") && d["campaigns"].is_array() &&
        !d["campaigns"].empty()) {
        ui::SectionLabel("ASSOCIATED CAMPAIGNS", box.x, y);
        y += 24.0f;
        for (const auto& c : d["campaigns"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(c, "name"), "SEARCH THE WEB >", false,
                        theme::ACCENT)) {
                a.kind = Action::OpenApp;
                a.app = "websearch";
                a.query = jstr(c, "name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    if (d.contains("infrastructure") && d["infrastructure"].is_array() &&
        !d["infrastructure"].empty()) {
        ui::SectionLabel("ASSOCIATED INFRASTRUCTURE", box.x, y);
        y += 24.0f;
        for (const auto& ip : d["infrastructure"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(ip, "ip_address"), "VIEW IN INTELSEARCH >",
                        false, theme::ACCENT)) {
                a.kind = Action::OpenApp;
                a.app = "intelsearch";
                a.query = jstr(ip, "ip_address");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    return PinButton(s, "malware", jint(d, "malware_id"), jstr(d, "family_name"),
                     box, y, a);
}

// -------------------------------------------------------------- campaign

float Campaign(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("CAMPAIGN", jstr(d, "name"), "", box, y);
    y = Field("Active since", Or(jstr(d, "active_since"), "unknown"), box, y);
    y += 6.0f;
    y += theme::TextWrapped(theme::UI(), jstr(d, "description"),
                            {box.x, y, box.width - 20.0f, 200.0f}, FS,
                            theme::TEXT);
    y += 12.0f;

    if (d.contains("actors") && d["actors"].is_array() && !d["actors"].empty()) {
        ui::SectionLabel("ATTRIBUTED TO", box.x, y);
        y += 24.0f;
        for (const auto& ac : d["actors"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(ac, "alias"), "OPEN PROFILE >", false,
                        theme::NOISE)) {
                a.kind = Action::OpenApp;
                a.app = "directory";
                a.query = jstr(ac, "alias");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    if (d.contains("malware") && d["malware"].is_array() && !d["malware"].empty()) {
        ui::SectionLabel("MALWARE USED", box.x, y);
        y += 24.0f;
        for (const auto& mw : d["malware"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(mw, "family_name"), "VIEW >", false,
                        theme::DANGER)) {
                a.kind = Action::OpenApp;
                a.app = "malwaredb";
                a.query = jstr(mw, "family_name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    return PinButton(s, "campaign", jint(d, "campaign_id"), jstr(d, "name"), box,
                     y, a);
}

// ----------------------------------------------------------------- actor

float Actor(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("THREAT ACTOR ALIAS", jstr(d, "alias"), "", box, y);
    y = Field("Origin region", Or(jstr(d, "origin_region"), "unattributed"), box, y);
    y = Field("Motivation", Or(jstr(d, "motivation"), "unclear"), box, y);
    y = Field("First attributed", Or(jstr(d, "first_attributed"), "unknown"), box, y);

    size_t nCamp = d.contains("campaigns") ? d["campaigns"].size() : 0;
    size_t nDom = d.contains("known_domains") ? d["known_domains"].size() : 0;
    size_t nMal = d.contains("known_malware") ? d["known_malware"].size() : 0;
    y = Field("Known campaigns", std::to_string(nCamp), box, y);
    y = Field("Known infrastructure", std::to_string(nDom), box, y);
    y = Field("Known malware", std::to_string(nMal), box, y);
    y += 8.0f;

    y += theme::TextWrapped(theme::UI(), jstr(d, "notes"),
                            {box.x, y, box.width - 20.0f, 200.0f}, FS,
                            theme::TEXT_DIM);
    y += 12.0f;

    if (nCamp) {
        ui::SectionLabel("CAMPAIGNS", box.x, y);
        y += 24.0f;
        for (const auto& c : d["campaigns"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(c, "name"), "SEARCH THE WEB >", false,
                        theme::ACCENT)) {
                a.kind = Action::OpenApp;
                a.app = "websearch";
                a.query = jstr(c, "name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    if (nDom) {
        ui::SectionLabel("KNOWN INFRASTRUCTURE", box.x, y);
        y += 24.0f;
        for (const auto& dm : d["known_domains"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            if (ui::Row(row, jstr(dm, "domain_name"), "VIEW >", false,
                        theme::StatusColor(jstr(dm, "status")))) {
                a.kind = Action::OpenApp;
                a.app = "intelsearch";
                a.query = jstr(dm, "domain_name");
            }
            y += theme::ROW_H;
        }
        y += 12.0f;
    }

    return PinButton(s, "actor", jint(d, "actor_id"), jstr(d, "alias"), box, y, a);
}

// ---------------------------------------------------------------- person

float Person(Session& s, const json& d, Rectangle box, float y, Action& a) {
    y = Header("CIVILIAN RECORD", jstr(d, "full_name"), "", box, y);
    y = Field("Username", Or(jstr(d, "username"), "-"), box, y);
    y = Field("Email", Or(jstr(d, "email"), "-"), box, y);
    y = Field("Phone", Or(jstr(d, "phone"), "-"), box, y);
    y = Field("City", Or(jstr(d, "city"), "-"), box, y);
    y = Field("Country", Or(jstr(d, "country"), "-"), box, y);
    y = Field("Employer", Or(jstr(d, "employer"), "-"), box, y);
    y = Field("Job title", Or(jstr(d, "job_title"), "-"), box, y);
    y = Field("Last known IP", Or(jstr(d, "last_ip"), "-"), box, y);
    y = Field("MAC", Or(jstr(d, "mac_address"), "-"), box, y);

    long long breaches = jint(d, "breach_count");
    y = Field("Breach appearances", std::to_string(breaches), box, y,
              breaches > 0 ? theme::WARN : theme::TEXT);
    std::string src = jstr(d, "breach_sources");
    if (!src.empty()) y = Field("Breach sources", src, box, y, theme::WARN);

    if (d.contains("socials") && d["socials"].is_object() &&
        !d["socials"].empty()) {
        y += 10.0f;
        ui::SectionLabel("PUBLIC ACCOUNTS", box.x, y);
        y += 24.0f;
        for (auto it = d["socials"].begin(); it != d["socials"].end(); ++it) {
            std::string v = it->is_string() ? it->get<std::string>() : it->dump();
            y = Field(it.key(), v, box, y);
        }
    }
    y += 10.0f;
    return PinButton(s, "person", jint(d, "person_id"), jstr(d, "full_name"), box,
                     y, a, false);
}

// --------------------------------------------------------------- article

float Article(Session& s, const json& d, Rectangle box, float y, Action& a) {
    (void)s;
    (void)a;
    Rectangle card{box.x, y, box.width - 14.0f, 0.0f};
    float inner = card.width - 24.0f;

    float titleH = theme::TextWrapped(theme::UI(), jstr(d, "title"),
                                      {0, 0, inner, 999}, 16.0f, theme::TEXT,
                                      false);
    float bodyH = theme::TextWrapped(theme::UI(), jstr(d, "body"),
                                     {0, 0, inner, 9999}, 13.5f, theme::TEXT,
                                     false);
    card.height = titleH + bodyH + 58.0f;

    DrawRectangleRec(card, theme::WIN_PANEL);
    DrawRectangleLinesEx(card, 1.0f, Color{216, 222, 230, 255});
    if (jbool(d, "reveals_alias"))
        DrawRectangleRec({card.x, card.y, 3.0f, card.height}, theme::ACCENT);

    float ty = card.y + 12.0f;
    theme::TextWrapped(theme::UI(), jstr(d, "title"),
                       {card.x + 14.0f, ty, inner, titleH + 2}, 16.0f,
                       theme::ACCENT_DARK);
    ty += titleH + 4.0f;
    theme::Text(theme::UI(),
                jstr(d, "outlet") + "  -  " + Or(jstr(d, "published"), "undated"),
                card.x + 14.0f, ty, 12.0f, theme::TEXT_DIM);
    ty += 20.0f;
    theme::TextWrapped(theme::UI(), jstr(d, "body"),
                       {card.x + 14.0f, ty, inner, bodyH + 2}, 13.5f, theme::TEXT);

    return y + card.height + 12.0f;
}

// -------------------------------------------------------------- envelope

float Empty(const std::string& message, Rectangle box, float y) {
    Rectangle card{box.x, y, box.width - 14.0f, 0.0f};
    float h = theme::TextWrapped(theme::UI(), message,
                                 {0, 0, card.width - 28.0f, 999}, 14.0f,
                                 theme::TEXT, false);
    card.height = h + 28.0f;
    DrawRectangleRec(card, Color{250, 246, 236, 255});
    DrawRectangleLinesEx(card, 1.0f, Color{226, 214, 190, 255});
    theme::TextWrapped(theme::UI(), message,
                       {card.x + 14.0f, card.y + 14.0f, card.width - 28.0f, h + 2},
                       14.0f, Color{122, 96, 40, 255});
    return y + card.height + 12.0f;
}

float Envelope(Session& s, const json& env, Rectangle box, float y, Action& a) {
    auto section = [&](const char* key,
                       float (*fn)(Session&, const json&, Rectangle, float,
                                   Action&)) {
        if (!env.contains(key) || !env[key].is_array()) return;
        for (const auto& item : env[key]) {
            y = fn(s, item, box, y, a);
            y += 10.0f;
            ui::Divider(box.x, y, box.width - 14.0f);
            y += 14.0f;
        }
    };

    section("domains", &Domain);
    section("ips", &Ip);
    section("malware", &Malware);
    section("campaigns", &Campaign);
    section("actors", &Actor);
    section("persons", &Person);

    if (env.contains("articles") && env["articles"].is_array()) {
        for (const auto& item : env["articles"]) y = Article(s, item, box, y, a);
    }
    return y;
}

}  // namespace rec
