// CaseDesk: where a case arrives and where hints are requested.
// CaseReport: where the player commits to a conclusion and is graded.
#include <algorithm>
#include <string>
#include <vector>

#include "../core/theme.h"
#include "../ui/widgets.h"
#include "common.h"
#include "factories.h"

namespace {

// ===================================================================== desk

class CaseDeskApp : public App {
  public:
    std::string Id() const override { return "casedesk"; }
    std::string Title() const override { return "CaseDesk - Incident Queue"; }
    std::string Glyph() const override { return "CD"; }
    Color Accent() const override { return theme::ACCENT_DARK; }
    bool RequiresCase() const override { return false; }
    Vector2 DefaultSize() const override { return Vector2{820.0f, 600.0f}; }

    void Draw(Session& s, Rectangle c, bool active) override {
        (void)active;
        if (hintReq_.ready()) {
            net::Response r = hintReq_.take();
            if (r.ok()) {
                try {
                    json h = json::parse(r.body);
                    s.lastHint = jstr(h, "body");
                    s.notify("Hint used. -" + std::to_string(jint(h, "penalty_applied")) +
                             " points at submission.");
                    s.refreshBrief();
                } catch (const std::exception&) {
                    s.notify("Could not decode the hint.", true);
                }
            } else {
                s.notify("Hint service unavailable.", true);
            }
        }

        DrawRectangleRec(c, theme::WIN_BODY);
        if (!s.hasCase()) {
            DrawIntake(s, c);
            return;
        }

        // ---- ticket header
        Rectangle head{c.x, c.y, c.width, 66.0f};
        DrawRectangleRec(head, theme::TITLE_ACTIVE);
        theme::Text(theme::Mono(), "CASE #" + s.caseCode(), head.x + 14.0f,
                    head.y + 12.0f, 22.0f, theme::TITLE_TEXT);
        std::string diff = jstr(s.brief, "difficulty");
        std::transform(diff.begin(), diff.end(), diff.begin(), ::toupper);
        Color dc = diff == "HARD" ? theme::DANGER
                   : diff == "MEDIUM" ? theme::WARN : theme::OK;
        ui::Badge({head.x + 14.0f, head.y + 42.0f, 84.0f, 17.0f}, diff, dc);
        std::string st = s.solved() ? "CLOSED" : "OPEN";
        ui::Badge({head.x + 106.0f, head.y + 42.0f, 70.0f, 17.0f}, st,
                  s.solved() ? theme::OK : theme::TITLE_IDLE);

        std::string meta = "attempts " + std::to_string(jint(s.brief, "attempts")) +
                           "   hints " + std::to_string(jint(s.brief, "hints_used"));
        float mw = theme::TextW(theme::UI(), meta, 13.0f);
        theme::Text(theme::UI(), meta, head.x + head.width - mw - 14.0f,
                    head.y + 44.0f, 13.0f, Color{190, 205, 220, 255});

        // ---- action strip
        Rectangle strip{c.x, c.y + 66.0f, c.width, 44.0f};
        DrawRectangleRec(strip, Color{238, 241, 246, 255});
        float bx = strip.x + theme::PAD;
        std::string entry = jstr(s.brief, "entry_domain");
        if (ui::Button({bx, strip.y + 9.0f, 210.0f, 26.0f},
                       "OPEN DOMAIN IN INTELSEARCH", !entry.empty())) {
            s.requestOpen("intelsearch", entry);
        }
        bx += 220.0f;
        if (ui::Button({bx, strip.y + 9.0f, 120.0f, 26.0f}, "REQUEST HINT",
                       !s.solved() && !hintReq_.pending())) {
            std::string u = s.url("/api/cases/" + std::to_string(s.caseId) + "/hint");
            hintReq_.start([u]() { return net::Post(u, "{}"); });
        }
        bx += 130.0f;
        if (ui::Button({bx, strip.y + 9.0f, 120.0f, 26.0f}, "FILE REPORT")) {
            s.requestOpen("casereport");
        }
        bx += 130.0f;
        if (ui::Button({bx, strip.y + 9.0f, 110.0f, 26.0f}, "NEW CASE")) {
            showIntake_ = true;
        }

        // ---- body
        Rectangle body{c.x + theme::PAD, c.y + 118.0f, c.width - theme::PAD * 2.0f,
                       c.height - 128.0f};
        ui::BeginScroll(scroll_, body);
        float y = body.y - scroll_.y;

        if (!s.lastHint.empty()) {
            float h = theme::TextWrapped(theme::UI(), s.lastHint,
                                         {0, 0, body.width - 60.0f, 999}, 14.0f,
                                         theme::TEXT, false);
            Rectangle hint{body.x, y, body.width - 14.0f, h + 34.0f};
            DrawRectangleRec(hint, Color{246, 243, 226, 255});
            DrawRectangleRec({hint.x, hint.y, 4.0f, hint.height}, theme::WARN);
            theme::Text(theme::UI(), "ANALYST NOTE", hint.x + 16.0f, hint.y + 8.0f,
                        11.0f, Color{150, 108, 20, 255});
            theme::TextWrapped(theme::UI(), s.lastHint,
                               {hint.x + 16.0f, hint.y + 24.0f,
                                hint.width - 32.0f, h + 2},
                               14.0f, Color{92, 70, 18, 255});
            y += hint.height + 14.0f;
        }

        if (s.solved() && !jstr(s.brief, "resolution_text").empty()) {
            std::string res = jstr(s.brief, "resolution_text");
            float h = theme::TextWrapped(theme::Mono(), res,
                                         {0, 0, body.width - 60.0f, 9999}, 13.0f,
                                         theme::TEXT, false);
            Rectangle card{body.x, y, body.width - 14.0f, h + 30.0f};
            DrawRectangleRec(card, Color{234, 246, 238, 255});
            DrawRectangleRec({card.x, card.y, 4.0f, card.height}, theme::OK);
            theme::TextWrapped(theme::Mono(), res,
                               {card.x + 16.0f, card.y + 15.0f,
                                card.width - 32.0f, h + 2},
                               13.0f, Color{26, 78, 50, 255});
            y += card.height + 14.0f;
        }

        // the briefing itself, in a monospaced ticket panel
        std::string brief = jstr(s.brief, "briefing");
        float bh = theme::TextWrapped(theme::Mono(), brief,
                                      {0, 0, body.width - 56.0f, 99999}, 13.0f,
                                      theme::TEXT, false);
        Rectangle panel{body.x, y, body.width - 14.0f, bh + 28.0f};
        DrawRectangleRec(panel, theme::WIN_PANEL);
        DrawRectangleLinesEx(panel, 1.0f, Color{214, 220, 228, 255});
        theme::TextWrapped(theme::Mono(), brief,
                           {panel.x + 16.0f, panel.y + 14.0f, panel.width - 32.0f,
                            bh + 2},
                           13.0f, theme::TEXT);
        y += panel.height + 16.0f;

        ui::EndScroll(scroll_, body, y - (body.y - scroll_.y));

        if (showIntake_) DrawIntakeOverlay(s, c);
    }

  private:
    void DrawIntake(Session& s, Rectangle c) {
        Rectangle card{c.x + c.width * 0.5f - 280.0f, c.y + 70.0f, 560.0f, 340.0f};
        DrawRectangleRec(card, theme::WIN_PANEL);
        DrawRectangleLinesEx(card, 1.0f, Color{206, 214, 224, 255});
        DrawRectangleRec({card.x, card.y, card.width, 4.0f}, theme::ACCENT);

        theme::Text(theme::UI(), "INCIDENT QUEUE", card.x + 24.0f, card.y + 22.0f,
                    12.0f, theme::TEXT_DIM);
        theme::Text(theme::UI(), "No case assigned", card.x + 24.0f,
                    card.y + 40.0f, 22.0f, theme::TEXT);
        theme::TextWrapped(
            theme::UI(),
            "Pick a difficulty and the queue will hand you a fresh incident. "
            "Cases are generated when you ask for one, so the infrastructure, "
            "the malware family and the actor are different every time.\n\n"
            "Higher difficulty means more co-hosted domains that are not "
            "involved, more complete decoy chains, and a larger article corpus "
            "to read through.",
            {card.x + 24.0f, card.y + 76.0f, card.width - 48.0f, 140.0f}, 14.0f,
            theme::TEXT_DIM);

        const char* labels[3] = {"EASY", "MEDIUM", "HARD"};
        const char* keys[3] = {"easy", "medium", "hard"};
        for (int i = 0; i < 3; ++i) {
            Rectangle b{card.x + 24.0f + i * 172.0f, card.y + 232.0f, 160.0f, 40.0f};
            if (ui::Button(b, labels[i], !s.busy())) {
                s.startNewCase(keys[i]);
                showIntake_ = false;
            }
        }
        if (s.busy()) {
            ui::Spinner({card.x + card.width * 0.5f, card.y + 300.0f}, 12.0f,
                        theme::ACCENT);
        } else if (!s.online && !s.offlineReason.empty()) {
            theme::Text(theme::UI(), "Service: " + s.offlineReason,
                        card.x + 24.0f, card.y + 294.0f, 12.0f, theme::DANGER);
        }
    }

    void DrawIntakeOverlay(Session& s, Rectangle c) {
        DrawRectangleRec(c, Color{0, 0, 0, 120});
        Rectangle card{c.x + c.width * 0.5f - 240.0f,
                       c.y + c.height * 0.5f - 110.0f, 480.0f, 220.0f};
        DrawRectangleRec(card, theme::WIN_PANEL);
        DrawRectangleLinesEx(card, 1.0f, theme::WIN_BORDER);
        theme::Text(theme::UI(), "Request a new case?", card.x + 22.0f,
                    card.y + 20.0f, 18.0f, theme::TEXT);
        theme::TextWrapped(theme::UI(),
                           "The current case stays on file, but this window will "
                           "switch to the new one.",
                           {card.x + 22.0f, card.y + 48.0f, card.width - 44.0f, 60.0f},
                           13.0f, theme::TEXT_DIM);
        const char* labels[3] = {"EASY", "MEDIUM", "HARD"};
        const char* keys[3] = {"easy", "medium", "hard"};
        for (int i = 0; i < 3; ++i) {
            Rectangle b{card.x + 22.0f + i * 148.0f, card.y + 112.0f, 136.0f, 34.0f};
            if (ui::Button(b, labels[i], !s.busy())) {
                s.startNewCase(keys[i]);
                showIntake_ = false;
            }
        }
        if (ui::Button({card.x + card.width - 110.0f, card.y + 162.0f, 88.0f, 28.0f},
                       "CANCEL")) {
            showIntake_ = false;
        }
    }

    ui::Scroll scroll_;
    net::Async hintReq_;
    bool showIntake_ = false;
};

// =================================================================== report

class CaseReportApp : public App {
  public:
    std::string Id() const override { return "casereport"; }
    std::string Title() const override { return "Case Report - Final Conclusion"; }
    std::string Glyph() const override { return "CR"; }
    Color Accent() const override { return theme::WARN; }
    Vector2 DefaultSize() const override { return Vector2{760.0f, 620.0f}; }

    void OnOpen(Session& s, const std::string&) override { LoadOptions(s); }

    void Draw(Session& s, Rectangle c, bool active) override {
        (void)active;
        PollOptions(s);
        PollSubmit(s);

        DrawRectangleRec(c, theme::WIN_BODY);
        if (!s.hasCase()) {
            theme::TextWrapped(theme::UI(), "No case is open.",
                               {c.x + 16.0f, c.y + 16.0f, c.width - 32.0f, 60.0f},
                               14.0f, theme::TEXT_DIM);
            return;
        }

        Rectangle body{c.x + theme::PAD, c.y + theme::PAD,
                       c.width - theme::PAD * 2.0f, c.height - theme::PAD * 2.0f};
        ui::BeginScroll(scroll_, body);
        float y = body.y - scroll_.y;

        theme::Text(theme::UI(), "CASE #" + s.caseCode() + " - CONCLUSION",
                    body.x, y, 18.0f, theme::TEXT);
        y += 26.0f;
        y += theme::TextWrapped(
            theme::UI(),
            "You can only name entities you have actually surfaced during the "
            "investigation. Pinned evidence adjusts your score: supporting "
            "records add, irrelevant ones subtract.",
            {body.x, y, body.width - 20.0f, 80.0f}, 13.0f, theme::TEXT_DIM);
        y += 14.0f;

        if (optionsReq_.pending()) {
            ui::Spinner({body.x + 20.0f, y + 16.0f}, 12.0f, theme::ACCENT);
            theme::Text(theme::UI(), "Loading your findings...", body.x + 44.0f,
                        y + 10.0f, 13.0f, theme::TEXT_DIM);
            y += 44.0f;
        } else {
            y = Dropdown(s, "WHO IS RESPONSIBLE?", "actors", actorCombo_, body, y);
            y = Dropdown(s, "ASSOCIATED CAMPAIGN", "campaigns", campaignCombo_,
                         body, y);
            y = Dropdown(s, "PRIMARY MALICIOUS DOMAIN", "domains", domainCombo_,
                         body, y);
            y = Dropdown(s, "MALWARE FAMILY", "malware", malwareCombo_, body, y);
        }

        y += 6.0f;
        ui::SectionLabel("SUPPORTING EVIDENCE", body.x, y);
        y += 26.0f;
        if (s.evidence.contains("items") && s.evidence["items"].is_array() &&
            !s.evidence["items"].empty()) {
            for (const auto& it : s.evidence["items"]) {
                Rectangle row{body.x, y, body.width - 14.0f, theme::ROW_H};
                std::string kind = jstr(it, "entity_kind");
                std::transform(kind.begin(), kind.end(), kind.begin(), ::toupper);
                if (ui::Row(row, jstr(it, "label"), kind + "   UNPIN", false,
                            theme::TEXT_DIM)) {
                    s.unpinEvidence(jint(it, "evidence_id"));
                }
                y += theme::ROW_H;
            }
        } else {
            y += theme::TextWrapped(
                theme::UI(),
                "Nothing pinned. You can still submit, but a report with no "
                "supporting records scores lower.",
                {body.x, y, body.width - 20.0f, 60.0f}, 13.0f, theme::TEXT_DIM);
        }
        y += 18.0f;

        bool complete = actorCombo_.index >= 0 && campaignCombo_.index >= 0 &&
                        domainCombo_.index >= 0 && malwareCombo_.index >= 0;
        if (ui::Button({body.x, y, 200.0f, 36.0f}, "SUBMIT REPORT",
                       complete && !s.solved() && !submitReq_.pending())) {
            Submit(s);
        }
        if (ui::Button({body.x + 210.0f, y, 150.0f, 36.0f}, "REFRESH FINDINGS",
                       !optionsReq_.pending())) {
            LoadOptions(s);
            s.refreshEvidence();
        }
        if (!complete && !s.solved()) {
            theme::Text(theme::UI(), "All four fields are required.",
                        body.x + 374.0f, y + 12.0f, 13.0f, theme::TEXT_DIM);
        }
        y += 50.0f;

        if (!verdict_.empty()) y = DrawVerdict(body, y);

        ui::EndScroll(scroll_, body, y - (body.y - scroll_.y));
    }

  private:
    float Dropdown(Session& s, const std::string& label, const char* key,
                   ui::Combo& combo, Rectangle body, float y) {
        (void)s;
        theme::Text(theme::UI(), label, body.x, y, 12.0f, theme::ACCENT_DARK);
        y += 18.0f;
        std::vector<std::string>& items = labels_[key];
        ui::ComboW(combo, {body.x, y, std::min(body.width - 20.0f, 430.0f), 28.0f},
                   items, items.empty() ? "(nothing discovered yet)" : "select...");
        return y + 40.0f;
    }

    void LoadOptions(Session& s) {
        if (!s.hasCase() || optionsReq_.pending()) return;
        std::string u = s.url("/api/cases/" + std::to_string(s.caseId) +
                              "/report-options");
        optionsReq_.start([u]() { return net::Get(u); });
    }

    void PollOptions(Session& s) {
        if (!optionsReq_.ready()) return;
        net::Response r = optionsReq_.take();
        if (!r.ok()) {
            s.notify("Could not load your findings.", true);
            return;
        }
        try {
            options_ = json::parse(r.body);
        } catch (const std::exception&) {
            return;
        }
        for (const char* key : {"actors", "campaigns", "domains", "malware"}) {
            labels_[key].clear();
            ids_[key].clear();
            if (!options_.contains(key) || !options_[key].is_array()) continue;
            for (const auto& o : options_[key]) {
                labels_[key].push_back(jstr(o, "label"));
                ids_[key].push_back(jint(o, "entity_id"));
            }
        }
        actorCombo_.index = campaignCombo_.index = -1;
        domainCombo_.index = malwareCombo_.index = -1;
    }

    long long Pick(const char* key, const ui::Combo& c) const {
        auto it = ids_.find(key);
        if (it == ids_.end() || c.index < 0 || c.index >= (int)it->second.size())
            return 0;
        return it->second[c.index];
    }

    void Submit(Session& s) {
        json body{{"actor_id", Pick("actors", actorCombo_)},
                  {"campaign_id", Pick("campaigns", campaignCombo_)},
                  {"domain_id", Pick("domains", domainCombo_)},
                  {"malware_id", Pick("malware", malwareCombo_)}};
        std::string u = s.url("/api/cases/" + std::to_string(s.caseId) + "/submit");
        std::string payload = body.dump();
        submitReq_.start([u, payload]() { return net::Post(u, payload); });
    }

    void PollSubmit(Session& s) {
        if (!submitReq_.ready()) return;
        net::Response r = submitReq_.take();
        if (!r.ok()) {
            s.notify(r.status == 409 ? "This case is already closed."
                                     : "Submission failed.",
                     true);
            return;
        }
        try {
            verdict_ = json::parse(r.body);
        } catch (const std::exception&) {
            return;
        }
        if (jbool(verdict_, "is_correct")) {
            s.notify("Case solved. Score: " + std::to_string(jint(verdict_, "score")));
        } else {
            s.notify("Report returned. Check the field breakdown.", true);
        }
        s.refreshBrief();
    }

    float DrawVerdict(Rectangle body, float y) {
        bool ok = jbool(verdict_, "is_correct");
        Color tint = ok ? theme::OK : theme::DANGER;

        Rectangle head{body.x, y, body.width - 14.0f, 40.0f};
        DrawRectangleRec(head, ok ? Color{234, 246, 238, 255}
                                  : Color{250, 236, 236, 255});
        DrawRectangleRec({head.x, head.y, 4.0f, head.height}, tint);
        theme::Text(theme::UI(),
                    ok ? "REPORT ACCEPTED" : "REPORT RETURNED",
                    head.x + 16.0f, head.y + 6.0f, 16.0f, tint);
        theme::Text(theme::UI(),
                    "attempt " + std::to_string(jint(verdict_, "attempt_no")) +
                        "   score " + std::to_string(jint(verdict_, "score")),
                    head.x + 16.0f, head.y + 24.0f, 12.0f, theme::TEXT_DIM);
        y += 50.0f;

        if (verdict_.contains("verdicts") && verdict_["verdicts"].is_array()) {
            for (const auto& v : verdict_["verdicts"]) {
                bool good = jbool(v, "correct");
                Rectangle row{body.x, y, body.width - 14.0f, 24.0f};
                theme::Text(theme::UI(), good ? "OK " : "XX ", row.x, row.y + 4.0f,
                            13.0f, good ? theme::OK : theme::DANGER);
                theme::Text(theme::UI(), jstr(v, "field"), row.x + 30.0f,
                            row.y + 4.0f, 13.0f, theme::TEXT_DIM);
                theme::Text(theme::Mono(), jstr(v, "submitted", "(none)"),
                            row.x + 220.0f, row.y + 4.0f, 13.0f,
                            good ? theme::TEXT : theme::DANGER);
                y += 24.0f;
            }
            y += 10.0f;
        }

        std::string narrative = jstr(verdict_, "narrative");
        float h = theme::TextWrapped(theme::Mono(), narrative,
                                     {0, 0, body.width - 60.0f, 9999}, 13.0f,
                                     theme::TEXT, false);
        Rectangle card{body.x, y, body.width - 14.0f, h + 28.0f};
        DrawRectangleRec(card, theme::WIN_PANEL);
        DrawRectangleLinesEx(card, 1.0f, Color{214, 220, 228, 255});
        theme::TextWrapped(theme::Mono(), narrative,
                           {card.x + 16.0f, card.y + 14.0f, card.width - 32.0f,
                            h + 2},
                           13.0f, theme::TEXT);
        return y + card.height + 14.0f;
    }

    ui::Scroll scroll_;
    ui::Combo actorCombo_, campaignCombo_, domainCombo_, malwareCombo_;
    net::Async optionsReq_, submitReq_;
    json options_ = json::object();
    json verdict_ = json::object();
    std::map<std::string, std::vector<std::string>> labels_;
    std::map<std::string, std::vector<long long>> ids_;
};

}  // namespace

std::unique_ptr<App> MakeCaseDesk() { return std::make_unique<CaseDeskApp>(); }
std::unique_ptr<App> MakeCaseReport() { return std::make_unique<CaseReportApp>(); }
