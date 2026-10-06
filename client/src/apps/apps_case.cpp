// CaseDesk: where a case arrives and where hints are requested.
// CaseReport: where the player commits to a conclusion and is graded.
#include <algorithm>
#include <map>
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

        PollLists(s);

        DrawRectangleRec(c, theme::WIN_BODY);
        if (!s.hasCase()) {
            DrawIntake(s, c);
            return;
        }
        if (exhibitsFor_ != s.caseId && !exhibitsReq_.pending()) {
            exhibitsFor_ = s.caseId;
            exhibits_ = json::object();
            std::string u = s.url("/api/cases/" + std::to_string(s.caseId) + "/exhibits");
            exhibitsReq_.start([u]() { return net::Get(u); });
        }

        // ---- ticket header
        Rectangle head{c.x, c.y, c.width, 66.0f};
        DrawRectangleRec(head, theme::TITLE_ACTIVE);
        theme::Text(theme::Mono(), "CASE #" + s.caseCode(), head.x + 14.0f,
                    head.y + 12.0f, 22.0f, theme::TITLE_TEXT);
        std::string diff = jstr(s.brief, "difficulty");
        std::transform(diff.begin(), diff.end(), diff.begin(), ::toupper);
        Color dc = (diff == "HARD" || diff == "EXPERT") ? theme::DANGER
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

        // what the reporting party handed over
        ui::SectionLabel("EXHIBITS FROM THE REPORTING PARTY", body.x, y);
        y += 24.0f;
        y += theme::TextWrapped(theme::UI(),
                                "Everything the victim gave you. Pin the exhibit that started "
                                "it: your evidence chain has to connect back to it.",
                                {body.x, y, body.width - 20.0f, 60.0f}, 13.0f,
                                theme::TEXT_DIM);
        y += 10.0f;
        rec::Action action;
        if (exhibitsReq_.pending()) {
            ui::Spinner({body.x + 20.0f, y + 14.0f}, 10.0f, theme::ACCENT);
            y += 36.0f;
        } else if (exhibits_.contains("cards") && exhibits_["cards"].is_array()) {
            Rectangle area{body.x, y, body.width, body.height};
            for (const auto& card : exhibits_["cards"]) {
                y = rec::Card(s, card, area, y, action);
                y += 8.0f;
                ui::Divider(body.x, y, body.width - 14.0f);
                y += 14.0f;
            }
        }

        ui::EndScroll(scroll_, body, y - (body.y - scroll_.y));
        rec::Apply(s, action);

        if (showIntake_) DrawIntakeOverlay(s, c);
    }

  private:
    void DrawIntake(Session& s, Rectangle c) {
        Rectangle card{c.x + c.width * 0.5f - 290.0f, c.y + 50.0f, 580.0f, 400.0f};
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
            "Cases are generated when you ask for one, so the people, accounts, "
            "infrastructure and the crew behind it differ every time.\n\n"
            "Higher difficulty means more decoys, attacker infrastructure that "
            "nobody has flagged yet, planted false flags, and on HARD and "
            "EXPERT, unmasking the real person running the scheme.",
            {card.x + 24.0f, card.y + 76.0f, card.width - 48.0f, 140.0f}, 14.0f,
            theme::TEXT_DIM);

        theme::Text(theme::UI(), "SCAM TYPE", card.x + 24.0f, card.y + 222.0f, 12.0f,
                    theme::ACCENT_DARK);
        DifficultyButtons(s, card.x + 24.0f, card.y + 296.0f, 128.0f, 40.0f);
        ScenarioCombo(s, {card.x + 24.0f, card.y + 240.0f, card.width - 48.0f, 28.0f});
        if (s.busy()) {
            ui::Spinner({card.x + card.width * 0.5f, card.y + 366.0f}, 12.0f,
                        theme::ACCENT);
        } else if (!s.online && !s.offlineReason.empty()) {
            theme::Text(theme::UI(), "Service: " + s.offlineReason,
                        card.x + 24.0f, card.y + 360.0f, 12.0f, theme::DANGER);
        }
    }

    void DifficultyButtons(Session& s, float x, float y, float w, float h) {
        const char* labels[4] = {"EASY", "MEDIUM", "HARD", "EXPERT"};
        const char* keys[4] = {"easy", "medium", "hard", "expert"};
        for (int i = 0; i < 4; ++i) {
            if (ui::Button({x + i * (w + 8.0f), y, w, h}, labels[i], !s.busy())) {
                s.startNewCase(keys[i], ScenarioKey());
                showIntake_ = false;
            }
        }
    }

    // "Random" first, then every scam type the server offers (GET /scenarios).
    void ScenarioCombo(Session& s, Rectangle r) {
        if (scnKeys_.empty() && !scenariosReq_.pending() && !scenariosAsked_) {
            scenariosAsked_ = true;
            std::string u = s.url("/scenarios");
            scenariosReq_.start([u]() { return net::Get(u); });
        }
        std::vector<std::string> items{"Random (the queue decides)"};
        items.insert(items.end(), scnLabels_.begin(), scnLabels_.end());
        if (scnCombo_.index < 0) scnCombo_.index = 0;
        ui::ComboW(scnCombo_, r, items, "Random");
    }

    std::string ScenarioKey() const {
        if (scnCombo_.index <= 0 || scnCombo_.index > (int)scnKeys_.size()) return "random";
        return scnKeys_[scnCombo_.index - 1];
    }

    void PollLists(Session& s) {
        if (exhibitsReq_.ready()) {
            net::Response r = exhibitsReq_.take();
            if (r.ok()) {
                try {
                    exhibits_ = json::parse(r.body);
                } catch (const std::exception&) {
                    s.notify("Could not read the exhibits.", true);
                }
            }
        }
        if (scenariosReq_.ready()) {
            net::Response r = scenariosReq_.take();
            if (!r.ok()) {
                scenariosAsked_ = false;
                return;
            }
            try {
                json list = json::parse(r.body);
                scnKeys_.clear();
                scnLabels_.clear();
                for (const auto& sc : list) {
                    scnKeys_.push_back(jstr(sc, "key"));
                    scnLabels_.push_back(jstr(sc, "title"));
                }
            } catch (const std::exception&) {
            }
        }
    }

    void DrawIntakeOverlay(Session& s, Rectangle c) {
        DrawRectangleRec(c, Color{0, 0, 0, 120});
        Rectangle card{c.x + c.width * 0.5f - 280.0f,
                       c.y + c.height * 0.5f - 130.0f, 560.0f, 260.0f};
        DrawRectangleRec(card, theme::WIN_PANEL);
        DrawRectangleLinesEx(card, 1.0f, theme::WIN_BORDER);
        theme::Text(theme::UI(), "Request a new case?", card.x + 22.0f,
                    card.y + 20.0f, 18.0f, theme::TEXT);
        theme::TextWrapped(theme::UI(),
                           "The current case stays on file, but this window will "
                           "switch to the new one.",
                           {card.x + 22.0f, card.y + 48.0f, card.width - 44.0f, 60.0f},
                           13.0f, theme::TEXT_DIM);
        DifficultyButtons(s, card.x + 22.0f, card.y + 140.0f, 122.0f, 34.0f);
        ScenarioCombo(s, {card.x + 22.0f, card.y + 96.0f, card.width - 44.0f, 28.0f});
        if (ui::Button({card.x + card.width - 110.0f, card.y + 202.0f, 88.0f, 28.0f},
                       "CANCEL")) {
            showIntake_ = false;
        }
    }

    ui::Scroll scroll_;
    net::Async hintReq_, exhibitsReq_, scenariosReq_;
    json exhibits_ = json::object();
    long long exhibitsFor_ = -1;
    std::vector<std::string> scnKeys_, scnLabels_;
    ui::Combo scnCombo_;
    bool scenariosAsked_ = false;
    bool showIntake_ = false;
};

// =================================================================== report

// The form is built from the case: one field per conclusion the scenario asks
// for (GET /api/cases/{id}/report-options). Each field only lists entities of
// that kind the player has actually surfaced, so nothing can be guessed.
class CaseReportApp : public App {
  public:
    std::string Id() const override { return "casereport"; }
    std::string Title() const override { return "Case Report - Final Conclusion"; }
    std::string Glyph() const override { return "CR"; }
    Color Accent() const override { return theme::WARN; }
    Vector2 DefaultSize() const override { return Vector2{780.0f, 660.0f}; }

    void OnOpen(Session& s, const std::string&) override {
        LoadOptions(s);
        s.refreshEvidence();
    }

    void Draw(Session& s, Rectangle c, bool active) override {
        (void)active;
        PollOptions(s);
        PollSubmit(s);
        if (loadedFor_ != s.caseId) {   // a new case arrived while the window was open
            verdict_ = json::object();
            fields_.clear();
            LoadOptions(s);
        }

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
            "Each field lists only what you have surfaced in your tools. Your "
            "pinned evidence must connect the first exhibit to every conclusion: "
            "unsupported answers and red herrings on the board cost points.",
            {body.x, y, body.width - 20.0f, 80.0f}, 13.0f, theme::TEXT_DIM);
        y += 14.0f;

        int filled = 0;
        if (optionsReq_.pending() && fields_.empty()) {
            ui::Spinner({body.x + 20.0f, y + 16.0f}, 12.0f, theme::ACCENT);
            theme::Text(theme::UI(), "Loading your findings...", body.x + 44.0f,
                        y + 10.0f, 13.0f, theme::TEXT_DIM);
            y += 44.0f;
        } else {
            for (Field& f : fields_) {
                std::string label = f.label;
                std::transform(label.begin(), label.end(), label.begin(), ::toupper);
                theme::Text(theme::UI(), label, body.x, y, 12.0f, theme::ACCENT_DARK);
                y += 18.0f;
                ui::ComboW(f.combo, {body.x, y, std::min(body.width - 20.0f, 520.0f), 28.0f},
                           f.labels, f.labels.empty() ? "(nothing of this kind found yet)"
                                                      : "select...");
                if (f.combo.index >= 0) ++filled;
                y += 40.0f;
            }
        }

        y += 6.0f;
        ui::SectionLabel("SUPPORTING EVIDENCE", body.x, y);
        y += 26.0f;
        if (s.evidence.contains("items") && s.evidence["items"].is_array() &&
            !s.evidence["items"].empty()) {
            for (const auto& it : s.evidence["items"]) {
                Rectangle row{body.x, y, body.width - 14.0f, theme::ROW_H};
                std::string kind = jstr(it, "entity_kind");
                std::replace(kind.begin(), kind.end(), '_', ' ');
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
                "Nothing pinned. You can still submit, but conclusions with no "
                "supporting chain score lower.",
                {body.x, y, body.width - 20.0f, 60.0f}, 13.0f, theme::TEXT_DIM);
        }
        y += 18.0f;

        bool complete = !fields_.empty() && filled == (int)fields_.size();
        if (ui::Button({body.x, y, 200.0f, 36.0f}, "SUBMIT REPORT",
                       complete && !s.solved() && !submitReq_.pending())) {
            Submit(s);
        }
        if (ui::Button({body.x + 210.0f, y, 170.0f, 36.0f}, "REFRESH FINDINGS",
                       !optionsReq_.pending())) {
            LoadOptions(s);
            s.refreshEvidence();
        }
        if (!complete && !s.solved()) {
            theme::Text(theme::UI(),
                        std::to_string(filled) + " of " + std::to_string(fields_.size()) +
                            " conclusions filled.",
                        body.x + 394.0f, y + 12.0f, 13.0f, theme::TEXT_DIM);
        }
        y += 50.0f;

        if (!verdict_.empty()) y = DrawVerdict(body, y);

        ui::EndScroll(scroll_, body, y - (body.y - scroll_.y));
    }

  private:
    struct Field {
        std::string key, label;
        std::vector<std::string> labels;
        std::vector<long long> ids;
        ui::Combo combo;
    };

    void LoadOptions(Session& s) {
        if (!s.hasCase() || optionsReq_.pending()) return;
        loadedFor_ = s.caseId;
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
        json opts;
        try {
            opts = json::parse(r.body);
        } catch (const std::exception&) {
            return;
        }
        // keep each field's current pick if it is still offered
        std::vector<Field> next;
        if (opts.contains("fields") && opts["fields"].is_array()) {
            for (const auto& jf : opts["fields"]) {
                Field f;
                f.key = jstr(jf, "key");
                f.label = jstr(jf, "label");
                if (jf.contains("options") && jf["options"].is_array()) {
                    for (const auto& o : jf["options"]) {
                        f.labels.push_back(jstr(o, "label"));
                        f.ids.push_back(jint(o, "entity_id"));
                    }
                }
                for (const Field& old : fields_) {
                    if (old.key != f.key || old.combo.index < 0) continue;
                    long long picked = old.ids[old.combo.index];
                    for (size_t i = 0; i < f.ids.size(); ++i)
                        if (f.ids[i] == picked) f.combo.index = (int)i;
                }
                next.push_back(std::move(f));
            }
        }
        fields_ = std::move(next);
    }

    void Submit(Session& s) {
        json answers = json::object();
        for (const Field& f : fields_)
            if (f.combo.index >= 0 && f.combo.index < (int)f.ids.size())
                answers[f.key] = f.ids[f.combo.index];
        json body{{"answers", answers}};
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
            s.notify("Report returned. " + std::to_string(jint(verdict_, "correct_count")) +
                         " of " + std::to_string(jint(verdict_, "total")) + " correct.",
                     true);
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
                // on HARD/EXPERT a returned report does not say which field is wrong
                bool known = v.contains("correct") && v["correct"].is_boolean();
                bool good = jbool(v, "correct");
                Color c = !known ? theme::TEXT_DIM : good ? theme::OK : theme::DANGER;
                Rectangle row{body.x, y, body.width - 14.0f, 24.0f};
                theme::Text(theme::UI(), !known ? "?? " : good ? "OK " : "XX ", row.x,
                            row.y + 4.0f, 13.0f, c);
                theme::Text(theme::UI(), jstr(v, "field"), row.x + 30.0f, row.y + 4.0f,
                            13.0f, theme::TEXT_DIM);
                theme::Text(theme::Mono(), jstr(v, "submitted", "(none)"), row.x + 300.0f,
                            row.y + 4.0f, 13.0f, known && !good ? theme::DANGER : theme::TEXT);
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
        y += card.height + 14.0f;

        // what the desk wants you to learn from this case
        if (verdict_.contains("notes") && verdict_["notes"].is_array() &&
            !verdict_["notes"].empty()) {
            ui::SectionLabel("ANALYST FEEDBACK", body.x, y);
            y += 24.0f;
            for (const auto& n : verdict_["notes"]) {
                y += theme::TextWrapped(theme::UI(), "- " + n.get<std::string>(),
                                        {body.x, y, body.width - 20.0f, 200.0f}, 13.0f,
                                        theme::TEXT);
                y += 4.0f;
            }
        }
        return y + 10.0f;
    }

    ui::Scroll scroll_;
    std::vector<Field> fields_;
    net::Async optionsReq_, submitReq_;
    json verdict_ = json::object();
    long long loadedFor_ = -1;
};

}  // namespace

std::unique_ptr<App> MakeCaseDesk() { return std::make_unique<CaseDeskApp>(); }
std::unique_ptr<App> MakeCaseReport() { return std::make_unique<CaseReportApp>(); }
