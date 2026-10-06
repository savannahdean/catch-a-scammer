// Terminal version of the game loop, built on the same ApiClient the raylib UI uses.
// Good for testing the backend without the UI:   make smoke   then   ./build/api_smoke hard
#include <iostream>
#include <sstream>
#include <string>

#include "net/ApiClient.hpp"

using cas::json;

static void print(const cas::ApiResult& r) {
    if (!r.ok()) { std::cout << "  ! " << r.error << "\n"; return; }
    std::cout << r.body.dump(2) << "\n";
}

int main(int argc, char** argv) {
    std::string difficulty = argc > 1 ? argv[1] : "medium";
    std::string scenario = argc > 2 ? argv[2] : "random";   // e.g. ./api_smoke hard romance
    cas::ApiClient api("127.0.0.1", 8000);

    auto h = api.health();
    if (!h.ok()) { std::cerr << h.error << "\n"; return 1; }

    auto nc = api.newCase(difficulty, std::nullopt, scenario);
    if (!nc.ok()) { std::cerr << nc.error << "\n"; return 1; }
    std::cout << "\n== " << nc.body["case_code"].get<std::string>() << " (" << difficulty << ") ==\n"
              << nc.body["briefing"].get<std::string>() << "\n\n";
    auto em = api.email();
    if (em.ok())
        std::cout << em.body["raw_headers"].get<std::string>() << "\n\n" << em.body["body_text"].get<std::string>() << "\n";

    std::cout << "\ncommands: search|pdns|whois|ct|scan|malware|breach|web|dir <q>, entity|graph|add <id>,\n"
                 "          rimg|social|phone|sms|doc|audio|pay|complaints <q>, trail <id>,\n"
                 "          pivot <field> <value>, evidence, hint, submit, debrief, quit\n";
    std::string line;
    while (std::cout << "\n> " && std::getline(std::cin, line)) {
        std::istringstream in(line);
        std::string cmd, arg;
        in >> cmd;
        std::getline(in >> std::ws, arg);
        if (cmd == "quit") break;
        else if (cmd == "search") print(api.search(arg));
        else if (cmd == "pdns") print(api.pdns(arg));
        else if (cmd == "whois") print(api.whois(arg));
        else if (cmd == "ct") print(api.certSearch(arg));
        else if (cmd == "scan") print(api.urlScan(arg));
        else if (cmd == "malware") print(api.malware(arg));
        else if (cmd == "breach") print(api.breach(arg));
        else if (cmd == "web") print(api.webSearch(arg));
        else if (cmd == "dir") print(api.directory(arg));
        else if (cmd == "rimg") print(api.reverseImage(arg));
        else if (cmd == "social") print(api.social(arg));
        else if (cmd == "phone") print(api.phone(arg));
        else if (cmd == "sms") print(api.sms(arg));
        else if (cmd == "doc") print(api.document(arg));
        else if (cmd == "audio") print(api.audio(arg));
        else if (cmd == "pay") print(api.payment(arg));
        else if (cmd == "complaints") print(api.complaints(arg));
        else if (cmd == "trail") print(api.moneyTrail(arg));
        else if (cmd == "entity") print(api.entity(arg));
        else if (cmd == "graph") print(api.graph(arg));
        else if (cmd == "add") print(api.addEvidence(arg));
        else if (cmd == "evidence") print(api.evidence());
        else if (cmd == "hint") print(api.hint());
        else if (cmd == "debrief") print(api.debrief());
        else if (cmd == "pivot") {
            std::istringstream a(arg); std::string f, v; a >> f >> v; print(api.pivot(f, v));
        } else if (cmd == "submit") {
            json rep;
            auto info = api.caseInfo();   // fall back to a fixed set if the form isn't available
            std::vector<std::string> keys;
            if (nc.ok() && nc.body.contains("report_fields"))
                for (auto& f : nc.body["report_fields"]) keys.push_back(f["key"].get<std::string>());
            if (keys.empty()) keys = {"actor", "campaign", "primary_domain", "origin_ip", "person"};
            for (const auto& k : keys) {
                std::string v; std::cout << "  " << k << ": "; std::getline(std::cin, v);
                if (!v.empty()) rep[k] = v;
            }
            print(api.submit(rep));
        } else std::cout << "  ? unknown command\n";
    }
    return 0;
}
