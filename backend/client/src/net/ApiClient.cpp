// ApiClient.cpp
// httplib.h is included ONLY here. On Windows it pulls in <windows.h>, whose
// CloseWindow/ShowCursor/DrawText/Rectangle clash with raylib. Keeping it in its
// own translation unit (and never in a header) avoids that whole mess.
#if defined(_WIN32)
  #define WIN32_LEAN_AND_MEAN
  #define NOGDI
  #define NOUSER
  #define NOMINMAX
#endif
#include "httplib.h"

#include "net/ApiClient.hpp"

#include <cctype>
#include <cstdio>

namespace cas {

namespace {
ApiResult toResult(const httplib::Result& r) {
    ApiResult out;
    if (!r) {
        out.error = "Cannot reach game server (" + httplib::to_string(r.error()) + "). Is `make server` running?";
        return out;
    }
    out.status = r->status;
    out.body = json::parse(r->body, nullptr, /*allow_exceptions=*/false);
    if (!out.ok()) {
        if (out.body.is_object() && out.body.contains("detail"))
            out.error = out.body["detail"].is_string() ? out.body["detail"].get<std::string>() : out.body["detail"].dump();
        else
            out.error = "HTTP " + std::to_string(r->status);
    }
    return out;
}
}  // namespace

ApiClient::ApiClient(std::string host, int port) : host_(std::move(host)), port_(port) {}

std::string ApiClient::urlEncode(const std::string& s) {
    std::string out;
    char buf[4];
    for (unsigned char ch : s) {
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.' || ch == '~') out += static_cast<char>(ch);
        else { std::snprintf(buf, sizeof buf, "%%%02X", ch); out += buf; }
    }
    return out;
}

// A fresh client per request: httplib::Client is not safe to share across threads,
// and Pending/async calls run on worker threads.
ApiResult ApiClient::get(const std::string& path) const {
    httplib::Client cli(host_, port_);
    cli.set_connection_timeout(3);
    cli.set_read_timeout(20);          // case generation takes a moment
    return toResult(cli.Get(path));
}

ApiResult ApiClient::post(const std::string& path, const json& body) const {
    httplib::Client cli(host_, port_);
    cli.set_connection_timeout(3);
    cli.set_read_timeout(30);
    return toResult(cli.Post(path, body.dump(), "application/json"));
}

ApiResult ApiClient::del(const std::string& path) const {
    httplib::Client cli(host_, port_);
    cli.set_connection_timeout(3);
    return toResult(cli.Delete(path));
}

ApiResult ApiClient::health() const { return get("/health"); }

ApiResult ApiClient::newCase(const std::string& difficulty, std::optional<long long> seed,
                             const std::string& scenario) {
    json body = {{"difficulty", difficulty}, {"scenario", scenario}};
    if (seed) body["seed"] = *seed;
    ApiResult r = post("/cases", body);
    if (r.ok()) caseId_ = r.body.value("case_id", "");
    return r;
}

ApiResult ApiClient::caseInfo() const { return get(c("")); }
ApiResult ApiClient::email() const { return get(c("/email")); }
ApiResult ApiClient::search(const std::string& q) const { return get(c("/search?q=" + urlEncode(q))); }
ApiResult ApiClient::entity(const std::string& id) const { return get(c("/entity/" + id)); }
ApiResult ApiClient::pdns(const std::string& q) const { return get(c("/pdns?q=" + urlEncode(q))); }
ApiResult ApiClient::whois(const std::string& d) const { return get(c("/whois?domain=" + urlEncode(d))); }
ApiResult ApiClient::certSearch(const std::string& q) const { return get(c("/ct?q=" + urlEncode(q))); }
ApiResult ApiClient::urlScan(const std::string& q) const { return get(c("/urlscan?q=" + urlEncode(q))); }
ApiResult ApiClient::pivot(const std::string& f, const std::string& v) const {
    return get(c("/pivot?field=" + urlEncode(f) + "&value=" + urlEncode(v)));
}
ApiResult ApiClient::malware(const std::string& q) const { return get(c("/malware?q=" + urlEncode(q))); }
ApiResult ApiClient::breach(const std::string& q) const { return get(c("/breach?q=" + urlEncode(q))); }
ApiResult ApiClient::webSearch(const std::string& q) const { return get(c("/web?q=" + urlEncode(q))); }
ApiResult ApiClient::directory(const std::string& q) const { return get(c("/directory?q=" + urlEncode(q))); }
ApiResult ApiClient::reverseImage(const std::string& q) const { return get(c("/reverse_image?q=" + urlEncode(q))); }
ApiResult ApiClient::moneyTrail(const std::string& id, int maxDepth) const {
    return get(c("/money_trail?start=" + urlEncode(id) + "&max_depth=" + std::to_string(maxDepth)));
}
ApiResult ApiClient::social(const std::string& q) const { return get(c("/social?q=" + urlEncode(q))); }
ApiResult ApiClient::phone(const std::string& n) const { return get(c("/phone?number=" + urlEncode(n))); }
ApiResult ApiClient::sms(const std::string& q) const { return get(c("/sms?q=" + urlEncode(q))); }
ApiResult ApiClient::document(const std::string& q) const { return get(c("/document?q=" + urlEncode(q))); }
ApiResult ApiClient::audio(const std::string& q) const { return get(c("/audio?q=" + urlEncode(q))); }
ApiResult ApiClient::payment(const std::string& q) const { return get(c("/payment?q=" + urlEncode(q))); }
ApiResult ApiClient::complaints(const std::string& q) const { return get(c("/complaints?q=" + urlEncode(q))); }
ApiResult ApiClient::scenarios() const { return get("/scenarios"); }
ApiResult ApiClient::graph(const std::string& id) const { return get(c("/graph/" + id)); }
ApiResult ApiClient::evidence() const { return get(c("/evidence")); }
ApiResult ApiClient::addEvidence(const std::string& id, const std::string& note) const {
    json b = {{"entity_id", id}};
    if (!note.empty()) b["note"] = note;
    return post(c("/evidence"), b);
}
ApiResult ApiClient::removeEvidence(const std::string& id) const { return del(c("/evidence/" + id)); }
ApiResult ApiClient::hint() const { return post(c("/hint"), json::object()); }
ApiResult ApiClient::submit(const json& report) const { return post(c("/submit"), report); }
ApiResult ApiClient::debrief() const { return get(c("/debrief")); }
ApiResult ApiClient::abandon() const { return post(c("/abandon"), json::object()); }

}  // namespace cas
