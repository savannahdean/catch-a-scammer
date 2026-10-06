// ApiClient.hpp - the only file the raylib UI needs to talk to the game server.
//
// Every in-game app maps to one method (CaseDesk -> newCase/email, IntelSearch -> search,
// Evidence Map -> graph, ...). Results come back as nlohmann::json so each window can
// read exactly the fields it draws.
//
// Never block the raylib frame loop: use the *Async() helpers with Pending<T>
// and poll() once per frame (see the example at the bottom of this file).
#pragma once

#include <chrono>
#include <future>
#include <optional>
#include <string>
#include <vector>

#include "nlohmann/json.hpp"

namespace cas {

using json = nlohmann::json;

struct ApiResult {
    int status = 0;         // HTTP status, 0 = could not reach server
    json body;              // parsed JSON (null on transport error)
    std::string error;      // human readable; show it in a dialog

    bool ok() const { return status >= 200 && status < 300; }
};

class ApiClient {
public:
    explicit ApiClient(std::string host = "127.0.0.1", int port = 8000);

    // --- CaseDesk -------------------------------------------------------
    ApiResult health() const;
    // scenario: "random" (default) or a key from scenarios() — e.g. "romance", "vishing", "whaling".
    ApiResult newCase(const std::string& difficulty, std::optional<long long> seed = std::nullopt,
                      const std::string& scenario = "random");
    ApiResult caseInfo() const;
    ApiResult email() const;                       // the initial clue (raw headers + body)

    // --- investigation tools ---------------------------------------------
    ApiResult search(const std::string& q) const;                 // IntelSearch
    ApiResult entity(const std::string& entityId) const;          // detail card for any node
    ApiResult pdns(const std::string& domainOrIp) const;          // DNS history
    ApiResult whois(const std::string& domain) const;             // WHOIS history (all snapshots)
    ApiResult certSearch(const std::string& q) const;             // certificate transparency
    ApiResult urlScan(const std::string& q) const;                // URL scanner
    ApiResult pivot(const std::string& field, const std::string& value) const;
                                     // field: tracking_id | favicon | jarm | nameserver | registrant_email | imphash
    ApiResult malware(const std::string& q) const;                // family name, hash, imphash, filename
    ApiResult breach(const std::string& emailOrUsername) const;   // breach corpus lookup
    ApiResult webSearch(const std::string& q) const;              // fictional search engine
    ApiResult directory(const std::string& q) const;              // actors, aliases, personas, people

    // --- tools for the non-phishing scams ---------------------------------
    ApiResult reverseImage(const std::string& imageIdOrPhash) const;  // romance/catfish, pig-butchering
    ApiResult moneyTrail(const std::string& startEntityId, int maxDepth = 6) const; // BEC, romance, crypto
    ApiResult social(const std::string& q) const;                 // posts / DMs by text or handle
    ApiResult phone(const std::string& number) const;             // carrier / line-type / spam reports
    ApiResult sms(const std::string& q) const;                    // smishing messages
    ApiResult document(const std::string& q) const;               // advance-fee forged docs (+metadata via entity())
    ApiResult audio(const std::string& q) const;                  // vishing: transcript, voiceprint, synthetic score
    ApiResult payment(const std::string& q) const;                // mule accounts, gift cards, wallets
    ApiResult complaints(const std::string& q) const;             // other victims' reports (corroboration + noise)
    ApiResult scenarios() const;                                  // list available scam types + report fields

    // --- Evidence Map / board --------------------------------------------
    ApiResult graph(const std::string& entityId) const;           // neighbours of a node
    ApiResult evidence() const;
    ApiResult addEvidence(const std::string& entityId, const std::string& note = "") const;
    ApiResult removeEvidence(const std::string& entityId) const;

    // --- Case Report ------------------------------------------------------
    ApiResult hint() const;
    ApiResult submit(const json& report) const;   // {actor, campaign, primary_domain, origin_ip, person?, evidence?}
    ApiResult debrief() const;                    // unlocked after solve/abandon
    ApiResult abandon() const;

    void setCase(const std::string& caseId) { caseId_ = caseId; }
    const std::string& caseId() const { return caseId_; }

    // Run any call on a worker thread:  auto p = api.async([&]{ return api.search("x"); });
    template <class F>
    std::future<ApiResult> async(F&& fn) const { return std::async(std::launch::async, std::forward<F>(fn)); }

    static std::string urlEncode(const std::string& s);

private:
    ApiResult get(const std::string& path) const;
    ApiResult post(const std::string& path, const json& body) const;
    ApiResult del(const std::string& path) const;
    std::string c(const std::string& tail) const { return "/cases/" + caseId_ + tail; }

    std::string host_;
    int port_;
    std::string caseId_;
};

// Poll-once-per-frame wrapper so windows can show a spinner instead of freezing.
class Pending {
public:
    Pending() = default;
    explicit Pending(std::future<ApiResult> f) : fut_(std::move(f)) {}
    bool active() const { return fut_.valid(); }
    // Returns true exactly once, on the frame the result arrives.
    bool poll(ApiResult& out) {
        if (!fut_.valid()) return false;
        if (fut_.wait_for(std::chrono::seconds(0)) != std::future_status::ready) return false;
        out = fut_.get();
        return true;
    }
private:
    std::future<ApiResult> fut_;
};

}  // namespace cas

/* ---------------------------------------------------------------- example
   // IntelSearch window
   cas::Pending searching;
   cas::ApiResult results;

   if (GuiButton(searchBtn, "Search")) {
       std::string q = queryText;
       searching = cas::Pending(api.async([&api, q] { return api.search(q); }));
   }
   if (searching.poll(results)) {
       if (!results.ok()) showError(results.error);
       else for (auto& row : results.body) rows.push_back({row["kind"], row["value"], row["verdict"]});
   }
   if (searching.active()) DrawText("Querying...", x, y, 18, GRAY);
------------------------------------------------------------------------- */
