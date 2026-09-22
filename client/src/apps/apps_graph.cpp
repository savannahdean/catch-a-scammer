// The Evidence Map.
//
// The graph is the payoff of the generalized relationship table: the client
// receives untyped (src, dst, rel_type) triples and lays them out without
// knowing anything about what a domain or a campaign is.
//
// Layout is a small force-directed simulation -- repulsion between every pair,
// springs along edges, and a weak pull toward the centre. Nodes fade in as the
// player discovers them, which is what makes the map feel like it is growing.
#include <algorithm>
#include <cmath>
#include <map>
#include <string>
#include <vector>

#include "../core/theme.h"
#include "../ui/widgets.h"
#include "common.h"
#include "factories.h"

namespace {

struct Node {
    std::string id, kind, label, sublabel, status;
    long long entityId = 0;
    bool inEvidence = false;
    Vector2 pos{0, 0};
    Vector2 vel{0, 0};
    float age = 0.0f;      // fade-in
    bool placed = false;
};

struct Edge {
    std::string src, dst, label;
    float confidence = 1.0f;
};

Color KindColor(const std::string& k) {
    if (k == "domain") return theme::DANGER;
    if (k == "ip") return theme::ACCENT;
    if (k == "provider") return Color{88, 108, 130, 255};
    if (k == "malware") return Color{176, 66, 30, 255};
    if (k == "campaign") return theme::WARN;
    if (k == "actor") return theme::NOISE;
    if (k == "person") return theme::OK;
    if (k == "article") return Color{110, 122, 138, 255};
    return theme::TEXT_DIM;
}

std::string KindLabel(const std::string& k) {
    if (k == "ip") return "IP ADDRESS";
    if (k == "provider") return "HOSTING";
    if (k == "actor") return "THREAT ACTOR";
    if (k == "article") return "REPORTING";
    if (k == "person") return "PERSON";
    std::string up = k;
    std::transform(up.begin(), up.end(), up.begin(), ::toupper);
    return up;
}

class EvidenceMapApp : public App {
  public:
    std::string Id() const override { return "evidencemap"; }
    std::string Title() const override { return "Evidence Map - Relationships"; }
    std::string Glyph() const override { return "EM"; }
    Color Accent() const override { return theme::ACCENT; }
    Vector2 DefaultSize() const override { return Vector2{940.0f, 640.0f}; }

    void OnOpen(Session& s, const std::string&) override { Load(s); }

    void Draw(Session& s, Rectangle c, bool active) override {
        Poll(s);
        cooldown_ -= GetFrameTime();
        if (s.hasCase() && cooldown_ <= 0.0f && !req_.pending()) {
            cooldown_ = 3.0f;
            Load(s);
        }

        DrawRectangleRec(c, Color{18, 26, 34, 255});

        // ---- toolbar
        Rectangle bar{c.x, c.y, c.width, 40.0f};
        DrawRectangleRec(bar, Color{28, 38, 48, 255});
        float bx = bar.x + theme::PAD;
        if (ui::Button({bx, bar.y + 7.0f, 90.0f, 26.0f}, "REFRESH")) Load(s);
        bx += 98.0f;
        if (ui::Button({bx, bar.y + 7.0f, 90.0f, 26.0f}, "RE-LAYOUT")) {
            for (auto& kv : nodes_) kv.second.placed = false;
        }
        bx += 98.0f;
        if (ui::Button({bx, bar.y + 7.0f, 110.0f, 26.0f}, "RECENTER")) {
            pan_ = Vector2{0, 0};
            zoom_ = 1.0f;
        }
        bx += 118.0f;
        ui::Checkbox({bx, bar.y + 7.0f, 150.0f, 26.0f}, "Show edge labels",
                     showEdgeLabels_);

        std::string stat = std::to_string(nodes_.size()) + " nodes  /  " +
                           std::to_string(edges_.size()) + " links";
        float sw = theme::TextW(theme::UI(), stat, 13.0f);
        theme::Text(theme::UI(), stat, bar.x + bar.width - sw - 14.0f,
                    bar.y + 13.0f, 13.0f, Color{150, 170, 190, 255});

        Rectangle view{c.x, c.y + 40.0f, c.width - 250.0f, c.height - 40.0f};
        Rectangle side{c.x + c.width - 250.0f, c.y + 40.0f, 250.0f, c.height - 40.0f};

        if (!s.hasCase()) {
            theme::TextWrapped(theme::UI(), "No case is open.",
                               {view.x + 20.0f, view.y + 20.0f, 300.0f, 60.0f},
                               14.0f, Color{150, 170, 190, 255});
            return;
        }

        Simulate(view, active);
        DrawGraph(view);
        DrawSidebar(s, side);
    }

  private:
    // ------------------------------------------------------------- loading
    void Load(Session& s) {
        if (!s.hasCase() || req_.pending()) return;
        std::string u = s.url("/api/cases/" + std::to_string(s.caseId) + "/graph");
        req_.start([u]() { return net::Get(u); });
    }

    void Poll(Session& s) {
        if (!req_.ready()) return;
        net::Response r = req_.take();
        if (!r.ok()) return;
        json g;
        try {
            g = json::parse(r.body);
        } catch (const std::exception&) {
            return;
        }
        (void)s;

        std::map<std::string, Node> next;
        if (g.contains("nodes") && g["nodes"].is_array()) {
            for (const auto& n : g["nodes"]) {
                Node node;
                node.id = jstr(n, "node_id");
                node.kind = jstr(n, "kind");
                node.label = jstr(n, "label");
                node.sublabel = jstr(n, "sublabel");
                node.status = jstr(n, "status");
                node.entityId = jint(n, "entity_id");
                node.inEvidence = jbool(n, "in_evidence");
                auto old = nodes_.find(node.id);
                if (old != nodes_.end()) {
                    node.pos = old->second.pos;
                    node.vel = old->second.vel;
                    node.age = old->second.age;
                    node.placed = old->second.placed;
                }
                next[node.id] = node;
            }
        }
        edges_.clear();
        if (g.contains("edges") && g["edges"].is_array()) {
            for (const auto& e : g["edges"]) {
                Edge ed;
                ed.src = jstr(e, "src");
                ed.dst = jstr(e, "dst");
                ed.label = jstr(e, "label");
                ed.confidence = e.contains("confidence") && e["confidence"].is_number()
                                    ? (float)e["confidence"].get<double>()
                                    : 1.0f;
                edges_.push_back(ed);
            }
        }
        nodes_.swap(next);
        if (!nodes_.count(selected_)) selected_.clear();
    }

    // ------------------------------------------------------------- physics
    void Simulate(Rectangle view, bool active) {
        float dt = std::min(GetFrameTime(), 0.033f);

        // seed unplaced nodes on a ring so they do not all start superimposed
        int idx = 0;
        for (auto& kv : nodes_) {
            if (!kv.second.placed) {
                float a = (float)idx * 2.399963f;  // golden angle
                float r = 60.0f + 14.0f * idx;
                kv.second.pos = Vector2{cosf(a) * r, sinf(a) * r};
                kv.second.placed = true;
            }
            kv.second.age = std::min(1.0f, kv.second.age + dt * 2.5f);
            ++idx;
        }

        // repulsion
        for (auto it = nodes_.begin(); it != nodes_.end(); ++it) {
            for (auto jt = std::next(it); jt != nodes_.end(); ++jt) {
                Vector2 d{jt->second.pos.x - it->second.pos.x,
                          jt->second.pos.y - it->second.pos.y};
                float dist2 = d.x * d.x + d.y * d.y + 0.01f;
                float dist = sqrtf(dist2);
                float f = 46000.0f / dist2;
                f = std::min(f, 900.0f);
                Vector2 dir{d.x / dist, d.y / dist};
                it->second.vel.x -= dir.x * f * dt;
                it->second.vel.y -= dir.y * f * dt;
                jt->second.vel.x += dir.x * f * dt;
                jt->second.vel.y += dir.y * f * dt;
            }
        }

        // springs
        for (const Edge& e : edges_) {
            auto a = nodes_.find(e.src);
            auto b = nodes_.find(e.dst);
            if (a == nodes_.end() || b == nodes_.end()) continue;
            Vector2 d{b->second.pos.x - a->second.pos.x,
                      b->second.pos.y - a->second.pos.y};
            float dist = sqrtf(d.x * d.x + d.y * d.y) + 0.01f;
            float rest = 150.0f;
            float f = (dist - rest) * 1.9f;
            Vector2 dir{d.x / dist, d.y / dist};
            a->second.vel.x += dir.x * f * dt;
            a->second.vel.y += dir.y * f * dt;
            b->second.vel.x -= dir.x * f * dt;
            b->second.vel.y -= dir.y * f * dt;
        }

        // gravity toward origin + damping + integrate
        for (auto& kv : nodes_) {
            Node& n = kv.second;
            n.vel.x -= n.pos.x * 0.55f * dt;
            n.vel.y -= n.pos.y * 0.55f * dt;
            n.vel.x *= 0.86f;
            n.vel.y *= 0.86f;
            if (kv.first == dragging_) continue;
            n.pos.x += n.vel.x * dt;
            n.pos.y += n.vel.y * dt;
        }

        if (!active) return;

        // ---- interaction
        Vector2 m = GetMousePosition();
        bool inside = CheckCollisionPointRec(m, view);
        if (inside) {
            float wheel = GetMouseWheelMove();
            if (wheel != 0.0f)
                zoom_ = std::min(2.4f, std::max(0.35f, zoom_ + wheel * 0.12f));
        }

        if (inside && IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
            std::string hit = HitTest(view, m);
            if (!hit.empty()) {
                selected_ = hit;
                dragging_ = hit;
            } else {
                selected_.clear();
                panning_ = true;
                panStart_ = m;
                panOrigin_ = pan_;
            }
        }
        if (IsMouseButtonReleased(MOUSE_BUTTON_LEFT)) {
            dragging_.clear();
            panning_ = false;
        }
        if (!dragging_.empty() && IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
            Vector2 w = ScreenToWorld(view, m);
            Node& n = nodes_[dragging_];
            n.pos = w;
            n.vel = Vector2{0, 0};
        }
        if (panning_ && IsMouseButtonDown(MOUSE_BUTTON_LEFT)) {
            pan_.x = panOrigin_.x + (m.x - panStart_.x);
            pan_.y = panOrigin_.y + (m.y - panStart_.y);
        }
    }

    Vector2 WorldToScreen(Rectangle view, Vector2 p) const {
        return Vector2{view.x + view.width * 0.5f + pan_.x + p.x * zoom_,
                       view.y + view.height * 0.5f + pan_.y + p.y * zoom_};
    }

    Vector2 ScreenToWorld(Rectangle view, Vector2 p) const {
        return Vector2{(p.x - view.x - view.width * 0.5f - pan_.x) / zoom_,
                       (p.y - view.y - view.height * 0.5f - pan_.y) / zoom_};
    }

    std::string HitTest(Rectangle view, Vector2 m) const {
        for (const auto& kv : nodes_) {
            Vector2 sp = WorldToScreen(view, kv.second.pos);
            float w = NodeW(kv.second) * zoom_;
            float h = 34.0f * zoom_;
            Rectangle r{sp.x - w * 0.5f, sp.y - h * 0.5f, w, h};
            if (CheckCollisionPointRec(m, r)) return kv.first;
        }
        return std::string();
    }

    static float NodeW(const Node& n) {
        float w = theme::TextW(theme::Mono(), n.label, 13.0f) + 28.0f;
        return std::min(std::max(w, 110.0f), 240.0f);
    }

    // ------------------------------------------------------------ drawing
    void DrawGraph(Rectangle view) {
        BeginScissorMode((int)view.x, (int)view.y, (int)view.width,
                         (int)view.height);

        // faint grid so panning is legible
        for (float gx = fmodf(pan_.x, 40.0f); gx < view.width; gx += 40.0f)
            DrawLineEx({view.x + gx, view.y}, {view.x + gx, view.y + view.height},
                       1.0f, Color{255, 255, 255, 8});
        for (float gy = fmodf(pan_.y, 40.0f); gy < view.height; gy += 40.0f)
            DrawLineEx({view.x, view.y + gy}, {view.x + view.width, view.y + gy},
                       1.0f, Color{255, 255, 255, 8});

        for (const Edge& e : edges_) {
            auto a = nodes_.find(e.src);
            auto b = nodes_.find(e.dst);
            if (a == nodes_.end() || b == nodes_.end()) continue;
            Vector2 p1 = WorldToScreen(view, a->second.pos);
            Vector2 p2 = WorldToScreen(view, b->second.pos);
            bool touched = (e.src == selected_ || e.dst == selected_);
            unsigned char alpha = (unsigned char)(70 + 120 * e.confidence);
            Color col = touched ? Color{120, 200, 255, 230}
                                : Color{120, 150, 180, alpha};
            DrawLineEx(p1, p2, touched ? 2.4f : 1.4f, col);

            // arrow head
            Vector2 d{p2.x - p1.x, p2.y - p1.y};
            float len = sqrtf(d.x * d.x + d.y * d.y) + 0.01f;
            Vector2 dir{d.x / len, d.y / len};
            Vector2 tip{p2.x - dir.x * 22.0f, p2.y - dir.y * 22.0f};
            Vector2 n1{-dir.y, dir.x};
            DrawTriangle(tip,
                         {tip.x - dir.x * 9.0f + n1.x * 4.5f,
                          tip.y - dir.y * 9.0f + n1.y * 4.5f},
                         {tip.x - dir.x * 9.0f - n1.x * 4.5f,
                          tip.y - dir.y * 9.0f - n1.y * 4.5f},
                         col);

            if (showEdgeLabels_ && zoom_ > 0.7f) {
                Vector2 mid{(p1.x + p2.x) * 0.5f, (p1.y + p2.y) * 0.5f};
                float w = theme::TextW(theme::UI(), e.label, 11.0f);
                DrawRectangleRec({mid.x - w * 0.5f - 4, mid.y - 8, w + 8, 15},
                                 Color{18, 26, 34, 200});
                theme::Text(theme::UI(), e.label, mid.x - w * 0.5f, mid.y - 7.0f,
                            11.0f, Color{150, 178, 200, 255});
            }
        }

        for (const auto& kv : nodes_) {
            const Node& n = kv.second;
            Vector2 sp = WorldToScreen(view, n.pos);
            float w = NodeW(n) * zoom_;
            float h = 34.0f * zoom_;
            Rectangle r{sp.x - w * 0.5f, sp.y - h * 0.5f, w, h};
            if (r.x + r.width < view.x || r.x > view.x + view.width) continue;

            unsigned char a = (unsigned char)(255 * n.age);
            Color accent = KindColor(n.kind);
            Color fill = (kv.first == selected_) ? Color{42, 58, 74, a}
                                                 : Color{32, 44, 56, a};
            DrawRectangleRounded(r, 0.25f, 6, fill);
            DrawRectangleLinesEx(r, kv.first == selected_ ? 2.0f : 1.0f,
                                 kv.first == selected_
                                     ? Color{130, 200, 255, a}
                                     : Color{accent.r, accent.g, accent.b, a});
            DrawRectangleRec({r.x, r.y + 4.0f * zoom_, 3.0f, h - 8.0f * zoom_},
                             Color{accent.r, accent.g, accent.b, a});
            if (n.inEvidence) {
                DrawCircleV({r.x + r.width - 8.0f, r.y + 8.0f}, 4.0f,
                            Color{theme::WARN.r, theme::WARN.g, theme::WARN.b, a});
            }

            if (zoom_ > 0.55f) {
                BeginScissorMode((int)r.x, (int)r.y, (int)r.width, (int)r.height);
                theme::Text(theme::UI(), KindLabel(n.kind), r.x + 10.0f,
                            r.y + 4.0f, 9.0f,
                            Color{accent.r, accent.g, accent.b, a});
                theme::Text(theme::Mono(), n.label, r.x + 10.0f, r.y + 15.0f,
                            12.0f, Color{228, 236, 244, a});
                EndScissorMode();
            }
        }

        EndScissorMode();
    }

    void DrawSidebar(Session& s, Rectangle side) {
        DrawRectangleRec(side, Color{26, 34, 44, 255});
        DrawLineEx({side.x, side.y}, {side.x, side.y + side.height}, 1.0f,
                   Color{52, 66, 82, 255});
        float y = side.y + 14.0f;

        theme::Text(theme::UI(), "SELECTED NODE", side.x + 14.0f, y, 11.0f,
                    Color{120, 150, 180, 255});
        y += 22.0f;

        auto it = nodes_.find(selected_);
        if (it == nodes_.end()) {
            theme::TextWrapped(
                theme::UI(),
                "Click a node to inspect it.\n\nDrag to reposition. Drag empty "
                "space to pan, scroll to zoom.\n\nA gold dot marks a node you "
                "have pinned as evidence. Pinning does not make it correct.",
                {side.x + 14.0f, y, side.width - 28.0f, 240.0f}, 13.0f,
                Color{132, 152, 172, 255});
            DrawLegend(side, side.y + side.height - 190.0f);
            return;
        }

        const Node& n = it->second;
        Color accent = KindColor(n.kind);
        ui::Badge({side.x + 14.0f, y, 110.0f, 18.0f}, KindLabel(n.kind), accent);
        y += 26.0f;
        y += theme::TextWrapped(theme::Mono(), n.label,
                                {side.x + 14.0f, y, side.width - 28.0f, 60.0f},
                                14.0f, Color{230, 238, 246, 255});
        y += 6.0f;
        if (!n.sublabel.empty()) {
            theme::Text(theme::UI(), n.sublabel, side.x + 14.0f, y, 12.0f,
                        Color{132, 152, 172, 255});
            y += 18.0f;
        }
        if (!n.status.empty()) {
            theme::Text(theme::UI(), "status: " + n.status, side.x + 14.0f, y,
                        12.0f, theme::StatusColor(n.status));
            y += 20.0f;
        }
        y += 8.0f;

        int degree = 0;
        for (const Edge& e : edges_)
            if (e.src == n.id || e.dst == n.id) ++degree;
        theme::Text(theme::UI(), "connections: " + std::to_string(degree),
                    side.x + 14.0f, y, 12.0f, Color{132, 152, 172, 255});
        y += 26.0f;

        if (ui::Button({side.x + 14.0f, y, side.width - 28.0f, 30.0f},
                       "INVESTIGATE NODE")) {
            s.requestOpen(AppForKind(n.kind), n.label);
        }
        y += 38.0f;
        bool pinned = s.isPinned(n.kind, n.entityId);
        if (ui::Button({side.x + 14.0f, y, side.width - 28.0f, 30.0f},
                       pinned ? "IN EVIDENCE" : "ADD TO EVIDENCE", !pinned)) {
            s.pinEvidence(n.kind, n.entityId, n.label);
        }
        y += 38.0f;
        if (ui::Button({side.x + 14.0f, y, side.width - 28.0f, 30.0f},
                       "OPEN CASE FILE")) {
            s.requestOpen("casedesk");
        }

        DrawLegend(side, side.y + side.height - 190.0f);
    }

    void DrawLegend(Rectangle side, float y) {
        theme::Text(theme::UI(), "LEGEND", side.x + 14.0f, y, 11.0f,
                    Color{120, 150, 180, 255});
        y += 20.0f;
        const char* kinds[] = {"person", "domain", "ip", "provider",
                               "malware", "campaign", "actor", "article"};
        for (const char* k : kinds) {
            DrawRectangleRec({side.x + 14.0f, y + 3.0f, 10.0f, 10.0f},
                             KindColor(k));
            theme::Text(theme::UI(), KindLabel(k), side.x + 32.0f, y, 12.0f,
                        Color{150, 170, 190, 255});
            y += 18.0f;
        }
    }

    static std::string AppForKind(const std::string& k) {
        if (k == "malware") return "malwaredb";
        if (k == "actor" || k == "person") return "directory";
        if (k == "campaign" || k == "article") return "websearch";
        return "intelsearch";
    }

    std::map<std::string, Node> nodes_;
    std::vector<Edge> edges_;
    net::Async req_;
    std::string selected_, dragging_;
    Vector2 pan_{0, 0}, panStart_{0, 0}, panOrigin_{0, 0};
    float zoom_ = 1.0f;
    float cooldown_ = 0.0f;
    bool panning_ = false;
    bool showEdgeLabels_ = true;
};

}  // namespace

std::unique_ptr<App> MakeEvidenceMap() {
    return std::make_unique<EvidenceMapApp>();
}
