#include "session.h"

#include <cstdlib>

std::string jstr(const json& j, const char* key, const std::string& def) {
    if (!j.is_object()) return def;
    auto it = j.find(key);
    if (it == j.end() || it->is_null()) return def;
    if (it->is_string()) return it->get<std::string>();
    return it->dump();
}

long long jint(const json& j, const char* key, long long def) {
    if (!j.is_object()) return def;
    auto it = j.find(key);
    if (it == j.end() || it->is_null() || !it->is_number()) return def;
    return it->get<long long>();
}

bool jbool(const json& j, const char* key, bool def) {
    if (!j.is_object()) return def;
    auto it = j.find(key);
    if (it == j.end() || it->is_null() || !it->is_boolean()) return def;
    return it->get<bool>();
}

Session::Session() {
    const char* env = std::getenv("CAS_API");
    apiBase = env ? env : "http://127.0.0.1:8000";
    const char* who = std::getenv("CAS_PLAYER");
    playerName = who ? who : "investigator";
    evidence = json::object();
    brief = json::object();
}

std::string Session::url(const std::string& path, const net::Params& p) const {
    return net::BuildUrl(apiBase, path, p);
}

net::Params Session::caseParams(const net::Params& extra) const {
    net::Params p{{"case_id", std::to_string(caseId)}};
    for (const auto& kv : extra) p.push_back(kv);
    return p;
}

void Session::notify(const std::string& text, bool error) {
    toasts_.push_back(Toast{text, 4.5f, error});
    if (toasts_.size() > 5) toasts_.erase(toasts_.begin());
}

void Session::requestOpen(const std::string& app, const std::string& query) {
    opens_.push_back(OpenRequest{app, query});
}

bool Session::popOpenRequest(OpenRequest& out) {
    if (opens_.empty()) return false;
    out = opens_.front();
    opens_.erase(opens_.begin());
    return true;
}

bool Session::busy() const {
    return caseReq_.pending() || briefReq_.pending() || evidenceReq_.pending();
}

void Session::pingHealth() {
    if (healthReq_.pending()) return;
    std::string u = url("/health");
    healthReq_.start([u]() { return net::Get(u); });
}

void Session::startNewCase(const std::string& difficulty) {
    if (caseReq_.pending()) return;
    json body{{"difficulty", difficulty}, {"player", playerName}};
    std::string u = url("/api/cases");
    std::string payload = body.dump();
    notify("Requesting a new case file...");
    caseReq_.start([u, payload]() { return net::Post(u, payload); });
}

void Session::refreshBrief() {
    if (!hasCase() || briefReq_.pending()) return;
    std::string u = url("/api/cases/" + std::to_string(caseId));
    briefReq_.start([u]() { return net::Get(u); });
}

void Session::refreshEvidence() {
    if (!hasCase() || evidenceReq_.pending()) return;
    std::string u = url("/api/cases/" + std::to_string(caseId) + "/evidence");
    evidenceReq_.start([u]() { return net::Get(u); });
}

void Session::pinEvidence(const std::string& kind, long long entityId,
                          const std::string& label) {
    if (!hasCase() || evidenceReq_.pending()) return;
    json body{{"entity_kind", kind}, {"entity_id", entityId}};
    std::string u = url("/api/cases/" + std::to_string(caseId) + "/evidence");
    std::string payload = body.dump();
    pendingPinLabel_ = label;
    evidenceReq_.start([u, payload]() { return net::Post(u, payload); });
}

void Session::unpinEvidence(long long evidenceId) {
    if (!hasCase() || evidenceReq_.pending()) return;
    std::string u = url("/api/cases/" + std::to_string(caseId) + "/evidence/" +
                        std::to_string(evidenceId));
    pendingPinLabel_.clear();
    evidenceReq_.start([u]() { return net::Delete(u); });
}

bool Session::isPinned(const std::string& kind, long long entityId) const {
    if (!evidence.contains("items") || !evidence["items"].is_array()) return false;
    for (const auto& it : evidence["items"]) {
        if (jstr(it, "entity_kind") == kind && jint(it, "entity_id") == entityId)
            return true;
    }
    return false;
}

void Session::Update(float dt) {
    for (auto& t : toasts_) t.ttl -= dt;
    toasts_.erase(std::remove_if(toasts_.begin(), toasts_.end(),
                                 [](const Toast& t) { return t.ttl <= 0.0f; }),
                  toasts_.end());

    if (healthReq_.ready()) {
        net::Response r = healthReq_.take();
        online = r.ok();
        offlineReason = r.ok() ? "" : (r.error.empty()
                                           ? "API returned HTTP " + std::to_string(r.status)
                                           : r.error);
        if (!online)
            notify("Cannot reach the case management service. " + offlineReason, true);
    }

    if (caseReq_.ready()) {
        net::Response r = caseReq_.take();
        if (r.ok()) {
            try {
                brief = json::parse(r.body);
                caseId = jint(brief, "case_id", -1);
                evidence = json::object();
                lastHint.clear();
                online = true;
                notify("Case #" + caseCode() + " assigned (" +
                       jstr(brief, "difficulty") + ").");
                refreshEvidence();
                requestOpen("casedesk");
            } catch (const std::exception& e) {
                notify(std::string("Malformed case payload: ") + e.what(), true);
            }
        } else {
            notify(r.error.empty()
                       ? "Case service refused the request (HTTP " +
                             std::to_string(r.status) + ")"
                       : "Case service unreachable: " + r.error,
                   true);
            online = false;
        }
    }

    if (briefReq_.ready()) {
        net::Response r = briefReq_.take();
        if (r.ok()) {
            try {
                brief = json::parse(r.body);
            } catch (const std::exception&) {
            }
        }
    }

    if (evidenceReq_.ready()) {
        net::Response r = evidenceReq_.take();
        if (r.ok()) {
            try {
                evidence = json::parse(r.body);
                if (!pendingPinLabel_.empty()) {
                    notify("Pinned to evidence: " + pendingPinLabel_);
                    pendingPinLabel_.clear();
                }
            } catch (const std::exception&) {
            }
        } else if (r.status == 409) {
            notify("You have not discovered that yet.", true);
        } else {
            notify("Evidence update failed.", true);
        }
    }
}
