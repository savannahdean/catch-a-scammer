#pragma once
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

#include "../net/http.h"

using json = nlohmann::json;

// Safe accessors -- the API is allowed to omit optional fields.
std::string jstr(const json& j, const char* key, const std::string& def = "");
long long jint(const json& j, const char* key, long long def = 0);
bool jbool(const json& j, const char* key, bool def = false);

// One app asking the shell to open another with a query pre-filled, e.g.
// clicking [VIEW MALWARE] in IntelSearch opens MalwareDB on that family.
struct OpenRequest {
    std::string app;    // "casedesk" | "intelsearch" | "malwaredb" | ...
    std::string query;
};

struct Toast {
    std::string text;
    float ttl = 0.0f;
    bool error = false;
};

class Session {
  public:
    Session();

    // ---- configuration
    std::string apiBase;
    std::string playerName;

    // ---- current case
    long long caseId = -1;
    json brief;      // CaseBrief
    json evidence;   // EvidenceList
    std::string lastHint;
    bool online = false;
    std::string offlineReason;

    bool hasCase() const { return caseId > 0; }
    std::string caseCode() const { return jstr(brief, "case_code", "------"); }
    bool solved() const { return jstr(brief, "status") == "solved"; }

    // ---- helpers
    std::string url(const std::string& path, const net::Params& p = {}) const;
    net::Params caseParams(const net::Params& extra = {}) const;

    void notify(const std::string& text, bool error = false);
    const std::vector<Toast>& toasts() const { return toasts_; }

    void requestOpen(const std::string& app, const std::string& query = "");
    bool popOpenRequest(OpenRequest& out);

    // ---- async operations owned by the shell
    void startNewCase(const std::string& difficulty);
    void refreshBrief();
    void refreshEvidence();
    void pinEvidence(const std::string& kind, long long entityId,
                     const std::string& label);
    void unpinEvidence(long long evidenceId);
    void pingHealth();

    bool isPinned(const std::string& kind, long long entityId) const;
    bool busy() const;

    // Called once per frame by the desktop.
    void Update(float dt);

  private:
    std::vector<Toast> toasts_;
    std::vector<OpenRequest> opens_;

    net::Async caseReq_, briefReq_, evidenceReq_, healthReq_;
    std::string pendingPinLabel_;
};
