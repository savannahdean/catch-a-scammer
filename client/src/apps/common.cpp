#include "common.h"

#include <algorithm>
#include <cstdio>
#include <utility>
#include <vector>

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
        case Action::FetchUrl:
            // outside a lookup window: let the target tool load the record
            s.requestOpen(a.app.empty() ? "intelsearch" : a.app, "@fetch:" + a.url);
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

// A strip of buttons that open other tools on the same value -- the pivots an
// analyst makes from a domain or an address without retyping it.
float PivotButtons(const std::vector<std::pair<std::string, std::string>>& apps,
                   const std::string& query, Rectangle box, float y, Action& a) {
    ui::SectionLabel("INVESTIGATE FURTHER", box.x, y);
    y += 24.0f;
    float x = box.x;
    for (const auto& [label, app] : apps) {
        float w = theme::TextW(theme::UI(), label, 12.0f) + 22.0f;
        if (x + w > box.x + box.width - 14.0f) {
            x = box.x;
            y += 30.0f;
        }
        if (ui::TinyButton({x, y, w, 24.0f}, label)) {
            a.kind = Action::OpenApp;
            a.app = app;
            a.query = query;
        }
        x += w + 6.0f;
    }
    return y + 36.0f;
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
    if (!jstr(d, "registered").empty())
        y = Field("Registered", jstr(d, "registered"), box, y);
    if (!jstr(d, "lookalike_of").empty())
        y = Field("Resembles", jstr(d, "lookalike_of"), box, y, theme::WARN);
    y += 8.0f;

    if (d.contains("associated_ips") && d["associated_ips"].is_array() &&
        !d["associated_ips"].empty()) {
        ui::SectionLabel("ASSOCIATED ADDRESSES", box.x, y);
        y += 24.0f;
        for (const auto& ip : d["associated_ips"]) {
            Rectangle row{box.x, y, box.width - 14.0f, theme::ROW_H};
            std::string span = jstr(ip, "first_seen");
            if (!span.empty()) span += " to " + jstr(ip, "last_seen") + "   ";
            if (ui::Row(row, jstr(ip, "ip_address"), span + "VIEW IP >", false,
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

    y = PivotButtons({{"DNS HISTORY", "dns"}, {"WHOIS HISTORY", "whois"},
                      {"CERTIFICATES", "certs"}, {"URL SCANS", "urlscan"},
                      {"WEB SEARCH", "websearch"}},
                     jstr(d, "domain_name"), box, y, a);
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
    if (!jstr(d, "reverse_dns").empty())
        y = Field("Reverse DNS", jstr(d, "reverse_dns"), box, y);
    if (!jstr(d, "tags").empty()) y = Field("Tags", jstr(d, "tags"), box, y, theme::WARN);
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

    y = PivotButtons({{"DNS HISTORY", "dns"}, {"URL SCANS", "urlscan"}},
                     jstr(d, "ip_address"), box, y, a);
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

    if (d.contains("attribution_sources") && d["attribution_sources"].is_array() &&
        !d["attribution_sources"].empty()) {
        ui::SectionLabel("WHO SAYS SO", box.x, y);
        y += 24.0f;
        for (const auto& src : d["attribution_sources"]) {
            y += theme::TextWrapped(theme::UI(), src.get<std::string>(),
                                    {box.x, y, box.width - 20.0f, 60.0f}, 13.0f,
                                    theme::TEXT_DIM);
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

// ------------------------------------------------------------------ card

namespace {

Color Tone(const std::string& t, Color def = theme::TEXT) {
    if (t == "danger") return theme::DANGER;
    if (t == "warn") return theme::WARN;
    if (t == "ok") return theme::OK;
    if (t == "dim") return theme::TEXT_DIM;
    return def;
}

// Shortens to fit a width, so a 64-character hash or a long URL never runs
// out of the window.
std::string Fit(const Font& f, const std::string& s, float size, float width) {
    if (theme::TextW(f, s, size) <= width) return s;
    std::string out = s;
    while (!out.empty() && theme::TextW(f, out + "...", size) > width) out.pop_back();
    return out + "...";
}

// A key/value line whose value wraps instead of running off the window.
float WrapField(const std::string& k, const std::string& v, Rectangle box, float y,
                Color c) {
    const float keyW = 170.0f;
    theme::Text(theme::UI(), k, box.x, y, 14.0f, theme::TEXT_DIM);
    float h = theme::TextWrapped(theme::Mono(), v,
                                 {box.x + keyW, y, box.width - keyW - 20.0f, 9999.0f},
                                 14.0f, c);
    return y + std::max(20.0f, h + 2.0f);
}

float Meter(const json& b, Rectangle box, float y) {
    ui::SectionLabel(jstr(b, "label"), box.x, y);
    y += 26.0f;
    double v = b.contains("value") && b["value"].is_number() ? b["value"].get<double>() : 0.0;
    v = std::min(std::max(v, 0.0), 1.0);
    float w = std::min(box.width - 120.0f, 420.0f);
    Rectangle track{box.x, y, w, 14.0f};
    DrawRectangleRec(track, Color{222, 226, 232, 255});
    Color fill = v >= 0.6 ? theme::DANGER : v >= 0.35 ? theme::WARN : theme::OK;
    DrawRectangleRec({track.x, track.y, (float)(track.width * v), track.height}, fill);
    DrawRectangleLinesEx(track, 1.0f, Color{170, 178, 190, 255});
    char buf[16];
    snprintf(buf, sizeof(buf), "%.2f", v);
    theme::Text(theme::Mono(), buf, track.x + track.width + 12.0f, y - 2.0f, 16.0f, fill);
    y += 18.0f;
    theme::Text(theme::UI(), jstr(b, "low"), track.x, y, 11.0f, theme::TEXT_DIM);
    std::string hi = jstr(b, "high");
    theme::Text(theme::UI(), hi, track.x + track.width - theme::TextW(theme::UI(), hi, 11.0f),
                y, 11.0f, theme::TEXT_DIM);
    y += 18.0f;
    if (!jstr(b, "note").empty())
        y += theme::TextWrapped(theme::UI(), jstr(b, "note"),
                                {box.x, y, box.width - 20.0f, 80.0f}, 12.5f,
                                theme::TEXT_DIM);
    return y + 10.0f;
}

// Terminal-style panel for raw tool output: headers, WHOIS, exiftool, YARA.
float MonoBlock(const json& b, Rectangle box, float y) {
    ui::SectionLabel(jstr(b, "label"), box.x, y);
    y += 24.0f;
    std::string t = jstr(b, "text");
    float inner = box.width - 46.0f;
    float h = theme::TextWrapped(theme::Mono(), t, {0, 0, inner, 99999.0f}, 12.5f,
                                 theme::TERM_TEXT, false);
    Rectangle panel{box.x, y, box.width - 14.0f, h + 20.0f};
    DrawRectangleRec(panel, theme::TERM_BG);
    theme::TextWrapped(theme::Mono(), t, {panel.x + 12.0f, panel.y + 10.0f, inner, h + 2.0f},
                       12.5f, theme::TERM_TEXT);
    return y + panel.height + 12.0f;
}

}  // namespace

float Card(Session& s, const json& c, Rectangle box, float y, Action& a) {
    float width = box.width - 14.0f;
    y = Header(jstr(c, "kind_label"),
               Fit(theme::Mono(), jstr(c, "title"), 16.0f, width - 150.0f),
               jstr(c, "status"), box, y);
    if (!jstr(c, "subtitle").empty()) {
        theme::Text(theme::UI(), Fit(theme::UI(), jstr(c, "subtitle"), 13.0f, width),
                    box.x, y - 2.0f, 13.0f, theme::TEXT_DIM);
        y += 20.0f;
    }

    if (c.contains("fields") && c["fields"].is_array()) {
        for (const auto& f : c["fields"]) {
            if (!f.is_array() || f.size() < 2) continue;
            std::string k = f[0].is_string() ? f[0].get<std::string>() : f[0].dump();
            std::string v = f[1].is_string() ? f[1].get<std::string>() : f[1].dump();
            std::string tone = f.size() > 2 && f[2].is_string() ? f[2].get<std::string>() : "";
            y = WrapField(k, v, box, y, Tone(tone));
        }
        y += 8.0f;
    }

    if (c.contains("blocks") && c["blocks"].is_array()) {
        for (const auto& b : c["blocks"]) {
            std::string type = jstr(b, "type");
            if (type == "text") {
                ui::SectionLabel(jstr(b, "label"), box.x, y);
                y += 24.0f;
                y += theme::TextWrapped(theme::UI(), jstr(b, "text"),
                                        {box.x, y, box.width - 20.0f, 99999.0f}, 14.0f,
                                        theme::TEXT);
                y += 12.0f;
            } else if (type == "mono") {
                y = MonoBlock(b, box, y);
            } else if (type == "meter") {
                y = Meter(b, box, y);
            } else if (type == "rows" && b.contains("rows") && b["rows"].is_array()) {
                ui::SectionLabel(jstr(b, "label"), box.x, y);
                y += 22.0f;
                if (!jstr(b, "note").empty()) {
                    y += theme::TextWrapped(theme::UI(), jstr(b, "note"),
                                            {box.x, y, box.width - 20.0f, 80.0f}, 12.5f,
                                            theme::TEXT_DIM);
                    y += 2.0f;
                }
                for (const auto& r : b["rows"]) {
                    Rectangle row{box.x, y, width, theme::ROW_H};
                    std::string right = jstr(r, "right");
                    float rw = theme::TextW(theme::UI(), right, 12.0f) + 30.0f;
                    std::string text = Fit(theme::Mono(), jstr(r, "text"), 14.0f,
                                           width - rw - 12.0f);
                    if (ui::Row(row, text, right, false, Tone(jstr(r, "tone"), theme::ACCENT))) {
                        if (r.contains("open")) {
                            a.kind = Action::OpenApp;
                            a.app = jstr(r["open"], "app");
                            a.query = jstr(r["open"], "query");
                        } else if (r.contains("fetch")) {
                            const json& f = r["fetch"];
                            net::Params extra;
                            if (f.contains("params") && f["params"].is_object())
                                for (auto it = f["params"].begin(); it != f["params"].end(); ++it)
                                    extra.push_back({it.key(), it->is_string()
                                                                   ? it->get<std::string>()
                                                                   : it->dump()});
                            a.kind = Action::FetchUrl;
                            a.app = jstr(f, "app");
                            a.url = s.url(jstr(f, "path"), s.caseParams(extra));
                        }
                    }
                    y += theme::ROW_H;
                }
                y += 12.0f;
            }
        }
    }

    if (c.contains("pin") && c["pin"].is_object())
        y = PinButton(s, jstr(c["pin"], "entity_kind"), jint(c["pin"], "entity_id"),
                      jstr(c["pin"], "label"), box, y, a);
    return y;
}

float Single(Session& s, const json& d, Rectangle box, float y, Action& a) {
    if (d.contains("card")) return Card(s, d, box, y, a);
    const std::string kind = jstr(d, "kind");
    if (kind == "domain") return Domain(s, d, box, y, a);
    if (kind == "ip") return Ip(s, d, box, y, a);
    if (kind == "malware") return Malware(s, d, box, y, a);
    if (kind == "campaign") return Campaign(s, d, box, y, a);
    if (kind == "actor") return Actor(s, d, box, y, a);
    if (kind == "person") return Person(s, d, box, y, a);
    if (kind == "article") return Article(s, d, box, y, a);
    return y;
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
    section("cards", &Card);

    if (env.contains("articles") && env["articles"].is_array()) {
        for (const auto& item : env["articles"]) y = Article(s, item, box, y, a);
    }
    return y;
}

}  // namespace rec
